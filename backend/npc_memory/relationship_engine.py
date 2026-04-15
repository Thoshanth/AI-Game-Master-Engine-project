import json
from backend.database.db import SessionLocal, NPC, Player
from backend.npc_memory.memory_store import get_all_memories_with_player
from backend.logger import get_logger

logger = get_logger("npc_memory.relationship")

# Relationship score thresholds and labels
RELATIONSHIP_LABELS = [
    (-1.0, -0.7, "mortal_enemy", "eyes you with murderous intent"),
    (-0.7, -0.4, "hostile", "regards you with open hostility"),
    (-0.4, -0.1, "unfriendly", "treats you with cold suspicion"),
    (-0.1, 0.1, "neutral", "regards you as a stranger"),
    (0.1, 0.4, "acquaintance", "recognizes you with mild warmth"),
    (0.4, 0.7, "friendly", "greets you with genuine warmth"),
    (0.7, 0.9, "trusted", "considers you a trusted friend"),
    (0.9, 1.01, "devoted", "would do almost anything for you"),
]


def get_relationship_info(score: float) -> dict:
    """Returns relationship label and description for a score."""
    for min_score, max_score, label, description in RELATIONSHIP_LABELS:
        if min_score <= score < max_score:
            return {
                "score": round(score, 3),
                "label": label,
                "description": description,
            }
    return {
        "score": round(score, 3),
        "label": "neutral",
        "description": "regards you as a stranger",
    }


def get_npc_relationship_with_player(
    npc_id: int,
    player_id: int,
) -> dict:
    """
    Returns complete relationship data between NPC and player.
    Includes score, label, history summary.
    """
    db = SessionLocal()
    try:
        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        if not npc:
            return {}

        relationships = json.loads(npc.relationships or "{}")
        player_key = f"player_{player_id}"
        score = relationships.get(player_key, 0.0)

        rel_info = get_relationship_info(score)

        # Get interaction history from memory
        memories = get_all_memories_with_player(npc_id, player_id)
        total_interactions = len(memories)
        positive = sum(
            1 for m in memories
            if m.get("relationship_delta", 0) > 0
        )
        negative = sum(
            1 for m in memories
            if m.get("relationship_delta", 0) < 0
        )

        return {
            "npc_id": npc_id,
            "npc_name": npc.name,
            "player_id": player_id,
            "relationship_score": score,
            "relationship_label": rel_info["label"],
            "relationship_description": rel_info["description"],
            "total_interactions": total_interactions,
            "positive_interactions": positive,
            "negative_interactions": negative,
            "first_met_day": (
                memories[0]["world_day"] if memories else None
            ),
            "most_impactful_memory": (
                max(memories, key=lambda m: abs(m.get("relationship_delta", 0)))["text"]
                if memories else None
            ),
        }
    finally:
        db.close()


def update_relationship_score(
    npc_id: int,
    player_id: int,
    delta: float,
    reason: str = "",
):
    """
    Updates the relationship score between NPC and player.
    delta: positive = more positive, negative = more negative
    Clamps to -1.0 to 1.0 range.
    """
    db = SessionLocal()
    try:
        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        if not npc:
            return

        relationships = json.loads(npc.relationships or "{}")
        player_key = f"player_{player_id}"
        current = relationships.get(player_key, 0.0)
        new_score = max(-1.0, min(1.0, current + delta))
        relationships[player_key] = new_score
        npc.relationships = json.dumps(relationships)
        db.commit()

        old_label = get_relationship_info(current)["label"]
        new_label = get_relationship_info(new_score)["label"]

        logger.debug(
            f"Relationship updated | npc='{npc.name}' | "
            f"player_id={player_id} | "
            f"{current:.2f} → {new_score:.2f} | "
            f"{old_label} → {new_label}"
        )

        # Log if relationship tier changed
        if old_label != new_label:
            logger.info(
                f"Relationship tier changed | npc='{npc.name}' | "
                f"player_id={player_id} | "
                f"{old_label} → {new_label} | reason='{reason}'"
            )

        return {
            "old_score": current,
            "new_score": new_score,
            "old_label": old_label,
            "new_label": new_label,
            "tier_changed": old_label != new_label,
        }

    finally:
        db.close()


def get_npc_behavior_from_relationship(
    relationship_score: float,
    npc_agreeableness: float = 5.0,
) -> dict:
    """
    Returns what behaviors are unlocked at this relationship level.
    High agreeableness = more behaviors unlocked at lower scores.
    """
    agree_bonus = (npc_agreeableness - 5.0) * 0.05

    return {
        "will_talk": relationship_score > -0.6,
        "will_trade": relationship_score > -0.3 + agree_bonus,
        "shares_rumors": relationship_score > 0.1 + agree_bonus,
        "shares_secrets": relationship_score > 0.5 + agree_bonus,
        "gives_discount": relationship_score > 0.4 + agree_bonus,
        "will_follow": relationship_score > 0.8 + agree_bonus,
        "reveals_quest": relationship_score > 0.3 + agree_bonus,
        "fights_alongside": relationship_score > 0.85 + agree_bonus,
        "attacks_on_sight": relationship_score < -0.8,
    }