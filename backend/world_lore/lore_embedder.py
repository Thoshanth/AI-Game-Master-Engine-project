"""
Embeds graph nodes and edges for semantic search.
Uses ChromaDB for vector storage and retrieval.
"""
import json
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
from backend.logger import get_logger

logger = get_logger("world_lore.embedder")


class LoreEmbedder:
    """
    Embeds knowledge graph elements for semantic search.
    
    Each node and edge is embedded as a document with:
    - Text description
    - Metadata (entity type, importance, timestamp)
    - Vector embedding for similarity search
    """
    
    def __init__(self, world_id: int):
        self.world_id = world_id
        self.collection_name = f"world_lore_{world_id}"
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(self.collection_name)
            logger.info(f"Loaded existing lore collection | world_id={world_id}")
        except:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"world_id": world_id}
            )
            logger.info(f"Created new lore collection | world_id={world_id}")
    
    def embed_graph(self, graph_dict: Dict):
        """
        Embeds all nodes and edges from a graph.
        
        Args:
            graph_dict: Graph exported to dictionary format
        """
        logger.info(f"Embedding graph | world_id={self.world_id}")
        
        documents = []
        metadatas = []
        ids = []
        
        # Embed nodes
        for node in graph_dict.get("nodes", []):
            doc_id = f"node_{node['id']}"
            
            # Create searchable text
            text = self._create_node_text(node)
            
            # Create metadata
            metadata = {
                "type": "node",
                "entity_type": node.get("entity_type", "unknown"),
                "entity_id": str(node.get("entity_id", "")),
                "name": node.get("name", ""),
                "importance": node.get("importance", 1.0),
            }
            
            documents.append(text)
            metadatas.append(metadata)
            ids.append(doc_id)
        
        # Embed edges
        for i, edge in enumerate(graph_dict.get("edges", [])):
            doc_id = f"edge_{i}"
            
            # Create searchable text
            text = self._create_edge_text(edge, graph_dict["nodes"])
            
            # Create metadata
            metadata = {
                "type": "edge",
                "relation": edge.get("relation", "unknown"),
                "source": edge.get("source", ""),
                "target": edge.get("target", ""),
                "world_day": edge.get("world_day", 0.0),
                "importance": edge.get("importance", 1.0),
            }
            
            documents.append(text)
            metadatas.append(metadata)
            ids.append(doc_id)
        
        # Add to ChromaDB in batches
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i+batch_size]
            batch_meta = metadatas[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]
            
            self.collection.upsert(
                documents=batch_docs,
                metadatas=batch_meta,
                ids=batch_ids
            )
        
        logger.info(
            f"Embedded {len(documents)} items | "
            f"nodes={len(graph_dict.get('nodes', []))} | "
            f"edges={len(graph_dict.get('edges', []))}"
        )
    
    def _create_node_text(self, node: Dict) -> str:
        """Create searchable text for a node."""
        entity_type = node.get("entity_type", "entity")
        name = node.get("name", "Unknown")
        description = node.get("description", "")
        
        text = f"{entity_type.title()}: {name}. {description}"
        
        # Add type-specific details
        if entity_type == "npc":
            role = node.get("role", "")
            is_alive = node.get("is_alive", True)
            status = "alive" if is_alive else "deceased"
            text += f" Role: {role}. Status: {status}."
        
        elif entity_type == "player":
            char_class = node.get("character_class", "")
            level = node.get("level", 1)
            text += f" Class: {char_class}. Level: {level}."
        
        elif entity_type == "location":
            loc_type = node.get("location_type", "")
            text += f" Type: {loc_type}."
        
        elif entity_type == "faction":
            faction_type = node.get("faction_type", "")
            motto = node.get("motto", "")
            text += f" Type: {faction_type}. Motto: {motto}."
        
        elif entity_type == "quest":
            quest_type = node.get("quest_type", "")
            state = node.get("state", "")
            text += f" Type: {quest_type}. State: {state}."
        
        elif entity_type == "item":
            item_type = node.get("item_type", "")
            rarity = node.get("rarity", "")
            text += f" Type: {item_type}. Rarity: {rarity}."
        
        return text
    
    def _create_edge_text(self, edge: Dict, nodes: List[Dict]) -> str:
        """Create searchable text for an edge."""
        relation = edge.get("relation", "related_to")
        description = edge.get("description", "")
        title = edge.get("title", "")
        
        # Find source and target node names
        source_id = edge.get("source", "")
        target_id = edge.get("target", "")
        
        source_name = "Unknown"
        target_name = "Unknown"
        
        for node in nodes:
            if node["id"] == source_id:
                source_name = node.get("name", "Unknown")
            if node["id"] == target_id:
                target_name = node.get("name", "Unknown")
        
        text = f"Event: {source_name} {relation.replace('_', ' ')} {target_name}."
        
        if title:
            text += f" {title}."
        
        if description:
            text += f" {description}"
        
        return text
    
    def search(
        self,
        query: str,
        n_results: int = 10,
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Semantic search over the knowledge graph.
        
        Args:
            query: Natural language query
            n_results: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of matching documents with metadata
        """
        logger.debug(f"Searching lore | query='{query[:50]}...'")
        
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=filter_metadata if filter_metadata else None
        )
        
        # Format results
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                formatted.append({
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None,
                })
        
        logger.debug(f"Found {len(formatted)} results")
        return formatted
    
    def search_by_entity(
        self,
        entity_type: str,
        entity_name: str,
        n_results: int = 5
    ) -> List[Dict]:
        """
        Search for a specific entity by type and name.
        
        Args:
            entity_type: Type of entity (npc, player, location, etc.)
            entity_name: Name of entity
            n_results: Number of results
            
        Returns:
            List of matching entities
        """
        query = f"{entity_type} named {entity_name}"
        
        results = self.search(
            query=query,
            n_results=n_results,
            filter_metadata={"entity_type": entity_type}
        )
        
        return results
    
    def search_by_time_range(
        self,
        query: str,
        start_day: float,
        end_day: float,
        n_results: int = 10
    ) -> List[Dict]:
        """
        Search for events within a time range.
        
        Args:
            query: Natural language query
            start_day: Start of time range (world days)
            end_day: End of time range (world days)
            n_results: Number of results
            
        Returns:
            List of matching events
        """
        # ChromaDB doesn't support range queries directly,
        # so we search and filter
        results = self.search(
            query=query,
            n_results=n_results * 2,  # Get more to filter
            filter_metadata={"type": "edge"}
        )
        
        # Filter by time range
        filtered = []
        for result in results:
            world_day = result["metadata"].get("world_day", 0.0)
            if start_day <= world_day <= end_day:
                filtered.append(result)
        
        return filtered[:n_results]
    
    def get_entity_by_id(self, entity_type: str, entity_id: int) -> Optional[Dict]:
        """
        Get a specific entity by ID.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            
        Returns:
            Entity document or None
        """
        doc_id = f"node_{entity_type}_{entity_id}"
        
        try:
            result = self.collection.get(ids=[doc_id])
            if result["ids"]:
                return {
                    "id": result["ids"][0],
                    "text": result["documents"][0],
                    "metadata": result["metadatas"][0],
                }
        except:
            pass
        
        return None
    
    def clear(self):
        """Clear all embeddings for this world."""
        try:
            self.client.delete_collection(self.collection_name)
            logger.info(f"Cleared lore collection | world_id={self.world_id}")
        except:
            pass
    
    def get_stats(self) -> Dict:
        """Get collection statistics."""
        count = self.collection.count()
        
        return {
            "world_id": self.world_id,
            "collection_name": self.collection_name,
            "total_documents": count,
        }
