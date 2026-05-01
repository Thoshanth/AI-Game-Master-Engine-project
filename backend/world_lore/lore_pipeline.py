"""
Main GraphRAG pipeline orchestrating graph building, retrieval, and synthesis.
"""
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from backend.world_lore.lore_graph import WorldLoreGraph
from backend.world_lore.lore_embedder import LoreEmbedder
from backend.world_lore.lore_retriever import LoreRetriever
from backend.world_lore.lore_synthesizer import LoreSynthesizer
from backend.logger import get_logger

logger = get_logger("world_lore.pipeline")


class LorePipeline:
    """
    Complete GraphRAG pipeline for world lore queries.
    
    Workflow:
    1. Build knowledge graph from world state
    2. Embed graph for semantic search
    3. Retrieve relevant information via hybrid search
    4. Synthesize natural language answer
    """
    
    def __init__(self, world_id: int):
        self.world_id = world_id
        self.graph = WorldLoreGraph(world_id)
        self.embedder = LoreEmbedder(world_id)
        self.retriever = LoreRetriever(world_id)
        self.synthesizer = LoreSynthesizer()
        
        self.graph_path = Path(f"game_data/lore_graphs/world_{world_id}_graph.json")
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
    
    def build_and_index(self, force_rebuild: bool = False):
        """
        Builds the knowledge graph and indexes it for search.
        
        Args:
            force_rebuild: If True, rebuilds even if graph exists
        """
        logger.info(f"Building lore index | world_id={self.world_id}")
        
        # Check if graph already exists
        if self.graph_path.exists() and not force_rebuild:
            logger.info("Loading existing graph")
            self._load_graph()
        else:
            logger.info("Building new graph from world state")
            # Build graph from database
            self.graph.build_from_world_state()
            
            # Save graph
            self._save_graph()
        
        # Embed graph for semantic search
        logger.info("Embedding graph for semantic search")
        graph_dict = self.graph.export_to_dict()
        self.embedder.embed_graph(graph_dict)
        
        # Update retriever's graph
        self.retriever.graph = self.graph
        
        logger.info(
            f"Lore index built | "
            f"nodes={self.graph.graph.number_of_nodes()} | "
            f"edges={self.graph.graph.number_of_edges()}"
        )
    
    def query(
        self,
        query: str,
        max_results: int = 10,
        max_hops: int = 2,
        time_range: Optional[Tuple[float, float]] = None,
    ) -> Dict:
        """
        Answers a natural language query about world lore.
        
        Args:
            query: Natural language question
            max_results: Maximum results to retrieve
            max_hops: Maximum graph hops
            time_range: Optional (start_day, end_day) filter
            
        Returns:
            Dict with answer and supporting information
        """
        logger.info(f"Lore query | query='{query[:50]}...'")
        
        # Ensure graph is built
        if self.graph.graph.number_of_nodes() == 0:
            logger.warning("Graph not built, building now")
            self.build_and_index()
        
        # Retrieve relevant information
        retrieval_result = self.retriever.retrieve(
            query=query,
            max_results=max_results,
            max_hops=max_hops,
            time_range=time_range,
        )
        
        # Synthesize answer
        answer = self.synthesizer.synthesize_query_answer(
            query, retrieval_result
        )
        
        return {
            "query": query,
            "answer": answer,
            "sources": {
                "nodes_found": retrieval_result["total_nodes"],
                "edges_found": retrieval_result["total_edges"],
                "top_entities": [
                    {
                        "name": node["name"],
                        "type": node["entity_type"],
                    }
                    for node in retrieval_result["top_nodes"][:5]
                ],
                "key_events": [
                    edge["description"]
                    for edge in retrieval_result["edges"][:3]
                    if edge.get("description")
                ],
            },
            "retrieval_details": retrieval_result,
        }
    
    def get_entity_history(
        self,
        entity_type: str,
        entity_name: str,
        include_narrative: bool = True
    ) -> Dict:
        """
        Gets complete history of a specific entity.
        
        Args:
            entity_type: Type of entity (npc, player, location, etc.)
            entity_name: Name of entity
            include_narrative: Whether to generate narrative summary
            
        Returns:
            Dict with entity history and optional narrative
        """
        logger.info(
            f"Entity history | type={entity_type} | name={entity_name}"
        )
        
        # Ensure graph is built
        if self.graph.graph.number_of_nodes() == 0:
            self.build_and_index()
        
        # Retrieve history
        history = self.retriever.retrieve_entity_history(
            entity_type, entity_name
        )
        
        if not history.get("found"):
            return history
        
        # Generate narrative if requested
        if include_narrative:
            narrative = self.synthesizer.synthesize_entity_summary(history)
            history["narrative"] = narrative
        
        return history
    
    def get_entity_connections(
        self,
        entity_type: str,
        entity_name: str,
        relation_type: Optional[str] = None,
        include_explanation: bool = True
    ) -> Dict:
        """
        Gets all connections for an entity.
        
        Args:
            entity_type: Type of entity
            entity_name: Name of entity
            relation_type: Optional filter by relation type
            include_explanation: Whether to generate explanation
            
        Returns:
            Dict with connections and optional explanation
        """
        logger.info(
            f"Entity connections | type={entity_type} | name={entity_name}"
        )
        
        # Ensure graph is built
        if self.graph.graph.number_of_nodes() == 0:
            self.build_and_index()
        
        # Retrieve connections
        connections = self.retriever.retrieve_connections(
            entity_type, entity_name, relation_type
        )
        
        if not connections.get("found"):
            return connections
        
        # Generate explanation if requested
        if include_explanation:
            explanation = self.synthesizer.synthesize_relationship_explanation(
                connections
            )
            connections["explanation"] = explanation
        
        return connections
    
    def get_timeline(
        self,
        start_day: float,
        end_day: float,
        event_types: Optional[list] = None,
        include_narrative: bool = True
    ) -> Dict:
        """
        Gets all events in a time period.
        
        Args:
            start_day: Start of period (world days)
            end_day: End of period (world days)
            event_types: Optional filter by event types
            include_narrative: Whether to generate narrative
            
        Returns:
            Dict with timeline and optional narrative
        """
        logger.info(
            f"Timeline | days {start_day:.1f} to {end_day:.1f}"
        )
        
        # Ensure graph is built
        if self.graph.graph.number_of_nodes() == 0:
            self.build_and_index()
        
        # Retrieve timeline
        timeline = self.retriever.retrieve_by_time_period(
            start_day, end_day, event_types
        )
        
        # Generate narrative if requested
        if include_narrative and timeline.get("events"):
            narrative = self.synthesizer.synthesize_timeline_narrative(
                timeline
            )
            timeline["narrative"] = narrative
        
        return timeline
    
    def rebuild_index(self):
        """Force rebuild of the entire lore index."""
        logger.info(f"Rebuilding lore index | world_id={self.world_id}")
        
        # Clear existing embeddings
        self.embedder.clear()
        
        # Rebuild
        self.build_and_index(force_rebuild=True)
        
        logger.info("Lore index rebuilt successfully")
    
    def get_stats(self) -> Dict:
        """Get statistics about the lore graph."""
        return {
            "world_id": self.world_id,
            "graph": {
                "nodes": self.graph.graph.number_of_nodes(),
                "edges": self.graph.graph.number_of_edges(),
            },
            "embeddings": self.embedder.get_stats(),
            "graph_file_exists": self.graph_path.exists(),
        }
    
    def _save_graph(self):
        """Save graph to disk."""
        graph_dict = self.graph.export_to_dict()
        
        with open(self.graph_path, 'w') as f:
            json.dump(graph_dict, f, indent=2)
        
        logger.debug(f"Graph saved to {self.graph_path}")
    
    def _load_graph(self):
        """Load graph from disk."""
        with open(self.graph_path, 'r') as f:
            graph_dict = json.load(f)
        
        # Rebuild graph from dict
        for node in graph_dict["nodes"]:
            node_id = node.pop("id")
            self.graph.graph.add_node(node_id, **node)
            self.graph.entity_index[node_id] = node_id
        
        for edge in graph_dict["edges"]:
            source = edge.pop("source")
            target = edge.pop("target")
            self.graph.graph.add_edge(source, target, **edge)
        
        logger.debug(f"Graph loaded from {self.graph_path}")


# Global pipeline cache
_pipelines = {}


def get_lore_pipeline(world_id: int) -> LorePipeline:
    """
    Get or create a lore pipeline for a world.
    
    Args:
        world_id: World ID
        
    Returns:
        LorePipeline instance
    """
    if world_id not in _pipelines:
        _pipelines[world_id] = LorePipeline(world_id)
    
    return _pipelines[world_id]


def clear_pipeline_cache():
    """Clear the pipeline cache."""
    global _pipelines
    _pipelines = {}
