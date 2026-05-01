"""
Hybrid retrieval: combines graph traversal with vector search.
Finds relevant information through both semantic similarity and graph connections.
"""
import json
from typing import List, Dict, Optional, Set, Tuple
from backend.world_lore.lore_graph import WorldLoreGraph
from backend.world_lore.lore_embedder import LoreEmbedder
from backend.logger import get_logger

logger = get_logger("world_lore.retriever")


class LoreRetriever:
    """
    Hybrid retrieval system combining:
    1. Vector search (semantic similarity)
    2. Graph traversal (relationship following)
    3. Temporal filtering (time-based queries)
    """
    
    def __init__(self, world_id: int):
        self.world_id = world_id
        self.graph = WorldLoreGraph(world_id)
        self.embedder = LoreEmbedder(world_id)
    
    def retrieve(
        self,
        query: str,
        max_results: int = 10,
        max_hops: int = 2,
        time_range: Optional[Tuple[float, float]] = None,
    ) -> Dict:
        """
        Main retrieval method combining all strategies.
        
        Args:
            query: Natural language query
            max_results: Maximum number of results
            max_hops: Maximum graph hops from seed nodes
            time_range: Optional (start_day, end_day) tuple
            
        Returns:
            Dict with retrieved nodes, edges, and paths
        """
        logger.info(f"Retrieving lore | query='{query[:50]}...'")
        
        # Step 1: Vector search to find seed nodes
        if time_range:
            vector_results = self.embedder.search_by_time_range(
                query, time_range[0], time_range[1], n_results=max_results
            )
        else:
            vector_results = self.embedder.search(query, n_results=max_results)
        
        # Step 2: Extract seed node IDs
        seed_nodes = set()
        for result in vector_results:
            if result["metadata"]["type"] == "node":
                # Extract node ID from doc ID (format: "node_npc_1")
                doc_id = result["id"]
                node_id = doc_id.replace("node_", "")
                seed_nodes.add(node_id)
            elif result["metadata"]["type"] == "edge":
                # Add both source and target
                seed_nodes.add(result["metadata"]["source"])
                seed_nodes.add(result["metadata"]["target"])
        
        logger.debug(f"Found {len(seed_nodes)} seed nodes from vector search")
        
        # Step 3: Graph traversal from seed nodes
        expanded_nodes = set(seed_nodes)
        expanded_edges = []
        
        for seed in seed_nodes:
            if seed not in self.graph.graph:
                continue
            
            # Get subgraph around this seed
            subgraph = self.graph.get_subgraph(seed, radius=max_hops)
            
            # Add all nodes and edges from subgraph
            expanded_nodes.update(subgraph.nodes())
            expanded_edges.extend([
                (source, target, data)
                for source, target, data in subgraph.edges(data=True)
            ])
        
        logger.debug(
            f"Expanded to {len(expanded_nodes)} nodes and "
            f"{len(expanded_edges)} edges"
        )
        
        # Step 4: Rank nodes by relevance
        ranked_nodes = self._rank_nodes(
            expanded_nodes, seed_nodes, vector_results
        )
        
        # Step 5: Find important paths between top nodes
        paths = self._find_important_paths(
            ranked_nodes[:5], max_hops=max_hops
        )
        
        return {
            "query": query,
            "seed_nodes": list(seed_nodes),
            "total_nodes": len(ranked_nodes),
            "total_edges": len(expanded_edges),
            "top_nodes": ranked_nodes[:max_results],
            "edges": [
                {
                    "source": source,
                    "target": target,
                    "relation": data.get("relation"),
                    "description": data.get("description"),
                    "world_day": data.get("world_day"),
                }
                for source, target, data in expanded_edges[:max_results]
            ],
            "paths": paths,
            "vector_results": vector_results[:5],
        }
    
    def _rank_nodes(
        self,
        nodes: Set[str],
        seed_nodes: Set[str],
        vector_results: List[Dict]
    ) -> List[Dict]:
        """
        Rank nodes by relevance.
        
        Scoring factors:
        - Is it a seed node? (high score)
        - Graph importance score
        - Vector search distance
        - Number of connections
        """
        scored_nodes = []
        
        # Create vector score lookup
        vector_scores = {}
        for result in vector_results:
            if result["metadata"]["type"] == "node":
                node_id = result["id"].replace("node_", "")
                # Lower distance = higher score
                vector_scores[node_id] = 1.0 - (result.get("distance", 1.0) / 2.0)
        
        for node_id in nodes:
            if node_id not in self.graph.graph:
                continue
            
            node_data = self.graph.get_node_data(node_id)
            
            score = 0.0
            
            # Seed node bonus
            if node_id in seed_nodes:
                score += 10.0
            
            # Graph importance
            score += node_data.get("importance", 1.0)
            
            # Vector similarity
            if node_id in vector_scores:
                score += vector_scores[node_id] * 5.0
            
            # Connection count
            degree = self.graph.graph.degree(node_id)
            score += min(degree * 0.5, 3.0)
            
            scored_nodes.append({
                "node_id": node_id,
                "score": score,
                "entity_type": node_data.get("entity_type"),
                "name": node_data.get("name"),
                "description": node_data.get("description", "")[:200],
                "importance": node_data.get("importance"),
            })
        
        # Sort by score
        scored_nodes.sort(key=lambda x: x["score"], reverse=True)
        
        return scored_nodes
    
    def _find_important_paths(
        self,
        top_nodes: List[Dict],
        max_hops: int = 3
    ) -> List[Dict]:
        """
        Find important paths between top nodes.
        
        Args:
            top_nodes: List of top-ranked nodes
            max_hops: Maximum path length
            
        Returns:
            List of path dictionaries
        """
        paths = []
        
        # Try to find paths between top nodes
        for i, node1 in enumerate(top_nodes[:3]):
            for node2 in top_nodes[i+1:4]:
                node1_id = node1["node_id"]
                node2_id = node2["node_id"]
                
                found_paths = self.graph.find_path(
                    node1_id, node2_id, max_hops=max_hops
                )
                
                for path in found_paths[:2]:  # Limit to 2 paths per pair
                    # Get path description
                    path_desc = self._describe_path(path)
                    
                    paths.append({
                        "start": node1["name"],
                        "end": node2["name"],
                        "length": len(path) - 1,
                        "nodes": path,
                        "description": path_desc,
                    })
        
        return paths[:5]  # Return top 5 paths
    
    def _describe_path(self, path: List[str]) -> str:
        """Create a human-readable description of a path."""
        if len(path) < 2:
            return ""
        
        descriptions = []
        
        for i in range(len(path) - 1):
            source = path[i]
            target = path[i + 1]
            
            # Get edge data
            edges = self.graph.graph.get_edge_data(source, target)
            if edges:
                # Get first edge
                edge_data = list(edges.values())[0]
                relation = edge_data.get("relation", "connected_to")
                
                source_name = self.graph.get_node_data(source).get("name", "Unknown")
                target_name = self.graph.get_node_data(target).get("name", "Unknown")
                
                descriptions.append(
                    f"{source_name} {relation.replace('_', ' ')} {target_name}"
                )
        
        return " → ".join(descriptions)
    
    def retrieve_entity_history(
        self,
        entity_type: str,
        entity_name: str,
        max_events: int = 20
    ) -> Dict:
        """
        Retrieve complete history of a specific entity.
        
        Args:
            entity_type: Type of entity (npc, player, location, etc.)
            entity_name: Name of entity
            max_events: Maximum number of events to return
            
        Returns:
            Dict with entity info and chronological timeline
        """
        logger.info(
            f"Retrieving entity history | "
            f"type={entity_type} | name={entity_name}"
        )
        
        # Find entity via vector search
        results = self.embedder.search_by_entity(
            entity_type, entity_name, n_results=1
        )
        
        if not results:
            return {
                "found": False,
                "message": f"No {entity_type} named '{entity_name}' found"
            }
        
        # Extract node ID
        node_id = results[0]["id"].replace("node_", "")
        
        # Get entity data
        entity_data = self.graph.get_node_data(node_id)
        
        # Get timeline
        timeline = self.graph.get_timeline(node_id)
        
        return {
            "found": True,
            "entity": {
                "node_id": node_id,
                "type": entity_data.get("entity_type"),
                "name": entity_data.get("name"),
                "description": entity_data.get("description"),
                "importance": entity_data.get("importance"),
            },
            "total_events": len(timeline),
            "timeline": timeline[:max_events],
        }
    
    def retrieve_connections(
        self,
        entity_type: str,
        entity_name: str,
        relation_type: Optional[str] = None
    ) -> Dict:
        """
        Retrieve all connections for an entity.
        
        Args:
            entity_type: Type of entity
            entity_name: Name of entity
            relation_type: Optional filter by relation type
            
        Returns:
            Dict with entity and all connections
        """
        # Find entity
        results = self.embedder.search_by_entity(
            entity_type, entity_name, n_results=1
        )
        
        if not results:
            return {
                "found": False,
                "message": f"No {entity_type} named '{entity_name}' found"
            }
        
        node_id = results[0]["id"].replace("node_", "")
        entity_data = self.graph.get_node_data(node_id)
        
        # Get neighbors
        neighbors = self.graph.get_neighbors(node_id, relation_type)
        
        # Format connections
        connections = []
        for neighbor_id, edge_data in neighbors:
            neighbor_data = self.graph.get_node_data(neighbor_id)
            
            connections.append({
                "target": {
                    "type": neighbor_data.get("entity_type"),
                    "name": neighbor_data.get("name"),
                },
                "relation": edge_data.get("relation"),
                "description": edge_data.get("description"),
            })
        
        return {
            "found": True,
            "entity": {
                "type": entity_data.get("entity_type"),
                "name": entity_data.get("name"),
            },
            "total_connections": len(connections),
            "connections": connections,
        }
    
    def retrieve_by_time_period(
        self,
        start_day: float,
        end_day: float,
        event_types: Optional[List[str]] = None,
        max_events: int = 50
    ) -> Dict:
        """
        Retrieve all events in a time period.
        
        Args:
            start_day: Start of period (world days)
            end_day: End of period (world days)
            event_types: Optional filter by event types
            max_events: Maximum events to return
            
        Returns:
            Dict with chronological events
        """
        logger.info(
            f"Retrieving time period | "
            f"days {start_day:.1f} to {end_day:.1f}"
        )
        
        # Get all edges with timestamps in range
        events = []
        
        for source, target, data in self.graph.graph.edges(data=True):
            world_day = data.get("world_day")
            
            if world_day is None:
                continue
            
            if start_day <= world_day <= end_day:
                # Filter by event type if specified
                if event_types and data.get("relation") not in event_types:
                    continue
                
                source_data = self.graph.get_node_data(source)
                target_data = self.graph.get_node_data(target)
                
                events.append({
                    "world_day": world_day,
                    "timestamp": data.get("timestamp"),
                    "relation": data.get("relation"),
                    "description": data.get("description"),
                    "source": {
                        "type": source_data.get("entity_type"),
                        "name": source_data.get("name"),
                    },
                    "target": {
                        "type": target_data.get("entity_type"),
                        "name": target_data.get("name"),
                    },
                    "importance": data.get("importance", 1.0),
                })
        
        # Sort by world_day
        events.sort(key=lambda e: e["world_day"])
        
        return {
            "start_day": start_day,
            "end_day": end_day,
            "total_events": len(events),
            "events": events[:max_events],
        }
