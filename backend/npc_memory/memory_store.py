import json
import uuid
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
from backend.database.world_store import get_npc
from backend.database.db import SessionLocal, NPC
from backend.logger import get_logger

logger = get_logger("npc_memory.store")

CHROMA_PATH = Path("chroma_db")
CHROMA_PATH.mkdir(exist_ok=True)

_chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
_embedder = None


def get_embedder() -> SentenceTransformer:
    """Lazy loads embedding model — cached after first call."""
    global _embedder
    if _embedder is None:
        logger.info("Loading NPC memory embedder...")
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("NPC memory embedder loaded")
    return _embedder


def get_npc_collection(npc_id: int):
    """
    Gets or creates a ChromaDB collection for one NPC.
    Each NPC has their own isolated memory space.

    Collection name: npc_{id}_memory
    """
    collection_name = f"npc_{npc_id}_memory"
    collection = _chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    # Store collection ID in NPC record if not already set
    db = SessionLocal()
    try:
        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        if npc and not npc.memory_collection_id:
            npc.memory_collection_id = collection_name
            db.commit()
    finally:
        db.close()

    return collection


def store_memory(
    npc_id: int,
    memory_text: str,
    player_id: int = None,
    event_type: str = "interaction",
    emotion_at_time: str = "neutral",
    relationship_delta: float = 0.0,
    world_day: float = 0.0,
    importance: int = 5,
    metadata_extra: dict = None,
):
    """
    Stores a new memory in an NPC's personal ChromaDB collection.

    memory_text: What the NPC experienced/observed
    importance: 1-10 (10 = life-changing, 1 = trivial)
    relationship_delta: how this event changed relationship score
    """
    collection = get_npc_collection(npc_id)
    embedder = get_embedder()

    # Generate embedding
    embedding = embedder.encode([memory_text])[0].tolist()

    # Build metadata
    metadata = {
        "npc_id": npc_id,
        "event_type": event_type,
        "emotion_at_time": emotion_at_time,
        "relationship_delta": relationship_delta,
        "world_day": world_day,
        "importance": importance,
    }
    if player_id is not None:
        metadata["player_id"] = player_id
    if metadata_extra:
        metadata.update(metadata_extra)

    memory_id = f"mem_{npc_id}_{uuid.uuid4().hex[:8]}"

    collection.upsert(
        ids=[memory_id],
        embeddings=[embedding],
        documents=[memory_text],
        metadatas=[metadata],
    )

    logger.debug(
        f"Memory stored | npc_id={npc_id} | "
        f"importance={importance} | event={event_type}"
    )
    return memory_id


def retrieve_relevant_memories(
    npc_id: int,
    query: str,
    player_id: int = None,
    n_results: int = 5,
    min_importance: int = 1,
) -> list[dict]:
    """
    Retrieves memories most relevant to the current conversation.

    Uses semantic search — not keyword matching.
    A query about "helping" retrieves memories of being helped
    even if exact words differ.

    Optionally filters to only memories involving a specific player.
    """
    collection = get_npc_collection(npc_id)

    if collection.count() == 0:
        logger.debug(f"No memories yet | npc_id={npc_id}")
        return []

    embedder = get_embedder()
    query_embedding = embedder.encode([query])[0].tolist()

    # Build filter
    where_filter = None
    if player_id is not None:
        where_filter = {"player_id": player_id}

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, collection.count()),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        memories = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            importance = meta.get("importance", 1)
            if importance >= min_importance:
                memories.append({
                    "text": doc,
                    "relevance": round(1 - dist, 3),
                    "importance": importance,
                    "event_type": meta.get("event_type"),
                    "emotion_at_time": meta.get("emotion_at_time"),
                    "world_day": meta.get("world_day", 0),
                    "player_id": meta.get("player_id"),
                    "relationship_delta": meta.get(
                        "relationship_delta", 0
                    ),
                })

        # Sort by combination of relevance and importance
        memories.sort(
            key=lambda m: (
                m["relevance"] * 0.6 + (m["importance"] / 10) * 0.4
            ),
            reverse=True,
        )

        logger.debug(
            f"Memories retrieved | npc_id={npc_id} | "
            f"found={len(memories)}"
        )
        return memories

    except Exception as e:
        logger.warning(f"Memory retrieval failed: {e}")
        return []


def get_all_memories_with_player(
    npc_id: int,
    player_id: int,
) -> list[dict]:
    """
    Returns ALL memories an NPC has of a specific player.
    Used to build the full relationship history.
    """
    collection = get_npc_collection(npc_id)

    if collection.count() == 0:
        return []

    try:
        results = collection.get(
            where={"player_id": player_id},
            include=["documents", "metadatas"],
        )

        memories = []
        for doc, meta in zip(
            results["documents"],
            results["metadatas"],
        ):
            memories.append({
                "text": doc,
                "importance": meta.get("importance", 1),
                "event_type": meta.get("event_type"),
                "emotion_at_time": meta.get("emotion_at_time"),
                "world_day": meta.get("world_day", 0),
                "relationship_delta": meta.get("relationship_delta", 0),
            })

        memories.sort(key=lambda m: m["world_day"])
        return memories

    except Exception as e:
        logger.warning(f"Memory fetch failed: {e}")
        return []


def get_memory_count(npc_id: int) -> int:
    """Returns total number of memories an NPC has."""
    collection = get_npc_collection(npc_id)
    return collection.count()