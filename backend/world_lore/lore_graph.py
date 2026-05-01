"""
Knowledge graph construction using NetworkX.
Converts world entities and events into a queryable graph structure.
"""
import json
import networkx as nx
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
from backend.database.db import (
    SessionLocal, World, NPC, Player, Location, 
    Faction, Quest, Item, WorldEvent, PlayerAction
)
from backend.logger import get_logger

logger = get_logger("world_lore.graph")


class WorldLoreGraph:
    """
    Knowledge graph of world history.
    
    Nodes represent entities:
    - NPCs, Players, Locations, Factions, Quests, Items
    
    Edges represent relationships and events:
    - killed_by, loved_by, occurred_at, caused_by, part_of
    
    Each node and edge has:
    - Attributes (name, description, properties)
    - Temporal data (when it was created/occurred)
    - Importance score (for ranking results)
    """
    
    def __init__(self, world_id: int):
        self.world_id = world_id
        self.graph = nx.MultiDiGraph()  # Directed graph with multiple edges
        self.entity_index = {}  # Fast lookup: entity_type_id -> node_id
        
    def build_from_world_state(self):
        """
        Builds the complete knowledge graph from current world state.
        
        Process:
        1. Add all entity nodes (NPCs, locations, factions, etc.)
        2. Add relationship edges (NPC at location, player in faction)
        3. Add event edges (deaths, trades, quests, wars)
        4. Calculate importance scores
        """
        logger.info(f"Building lore graph | world_id={self.world_id}")
        
        db = SessionLocal()
        try:
            # Step 1: Add entity nodes
            self._add_npc_nodes(db)
            self._add_player_nodes(db)
            self._add_location_nodes(db)
            self._add_faction_nodes(db)
            self._add_quest_nodes(db)
            self._add_item_nodes(db)
            
            # Step 2: Add relationship edges
            self._add_location_relationships(db)
            self._add_faction_relationships(db)
            self._add_npc_relationships(db)
            
            # Step 3: Add event edges
            self._add_world_events(db)
            self._add_player_actions(db)
            
            # Step 4: Calculate importance
            self._calculate_node_importance()
            
            logger.info(
                f"Graph built | nodes={self.graph.number_of_nodes()} | "
                f"edges={self.graph.number_of_edges()}"
            )
            
        finally:
            db.close()
    
    def _add_npc_nodes(self, db):
        """Add all NPCs as nodes."""
        npcs = db.query(NPC).filter(NPC.world_id == self.world_id).all()
        
        for npc in npcs:
            node_id = f"npc_{npc.id}"
            self.entity_index[node_id] = node_id
            
            self.graph.add_node(
                node_id,
                entity_type="npc",
                entity_id=npc.id,
                name=npc.name,
                role=npc.role,
                description=f"{npc.name}, a {npc.role}. {npc.backstory}",
                is_alive=npc.is_alive,
                location_id=npc.location_id,
                faction_id=npc.faction_id,
                personality={
                    "openness": npc.trait_openness,
                    "conscientiousness": npc.trait_conscientiousness,
                    "extraversion": npc.trait_extraversion,
                    "agreeableness": npc.trait_agreeableness,
                    "neuroticism": npc.trait_neuroticism,
                },
                importance=5.0,  # Base importance
            )
        
        logger.debug(f"Added {len(npcs)} NPC nodes")
    
    def _add_player_nodes(self, db):
        """Add all players as nodes."""
        players = db.query(Player).filter(Player.world_id == self.world_id).all()
        
        for player in players:
            node_id = f"player_{player.id}"
            self.entity_index[node_id] = node_id
            
            self.graph.add_node(
                node_id,
                entity_type="player",
                entity_id=player.id,
                name=player.character_name,
                username=player.username,
                character_class=player.character_class,
                description=f"{player.character_name}, a {player.character_class}",
                level=player.level,
                location_id=player.current_location_id,
                importance=8.0,  # Players are important
            )
        
        logger.debug(f"Added {len(players)} player nodes")
    
    def _add_location_nodes(self, db):
        """Add all locations as nodes."""
        locations = db.query(Location).join(Location.region).filter(
            Location.region.has(world_id=self.world_id)
        ).all()
        
        for location in locations:
            node_id = f"location_{location.id}"
            self.entity_index[node_id] = node_id
            
            self.graph.add_node(
                node_id,
                entity_type="location",
                entity_id=location.id,
                name=location.name,
                location_type=location.location_type,
                description=location.description,
                region_id=location.region_id,
                importance=4.0,
            )
        
        logger.debug(f"Added {len(locations)} location nodes")
    
    def _add_faction_nodes(self, db):
        """Add all factions as nodes."""
        factions = db.query(Faction).filter(Faction.world_id == self.world_id).all()
        
        for faction in factions:
            node_id = f"faction_{faction.id}"
            self.entity_index[node_id] = node_id
            
            self.graph.add_node(
                node_id,
                entity_type="faction",
                entity_id=faction.id,
                name=faction.name,
                faction_type=faction.faction_type,
                description=faction.description,
                motto=faction.motto,
                importance=7.0,  # Factions are important
            )
        
        logger.debug(f"Added {len(factions)} faction nodes")
    
    def _add_quest_nodes(self, db):
        """Add all quests as nodes."""
        quests = db.query(Quest).filter(Quest.world_id == self.world_id).all()
        
        for quest in quests:
            node_id = f"quest_{quest.id}"
            self.entity_index[node_id] = node_id
            
            self.graph.add_node(
                node_id,
                entity_type="quest",
                entity_id=quest.id,
                name=quest.title,
                quest_type=quest.quest_type,
                description=quest.description,
                state=quest.state,
                importance=6.0,
            )
        
        logger.debug(f"Added {len(quests)} quest nodes")
    
    def _add_item_nodes(self, db):
        """Add all items as nodes."""
        items = db.query(Item).filter(Item.world_id == self.world_id).all()
        
        for item in items:
            node_id = f"item_{item.id}"
            self.entity_index[node_id] = node_id
            
            rarity_importance = {
                "common": 2.0,
                "uncommon": 3.0,
                "rare": 5.0,
                "legendary": 9.0,
            }
            
            self.graph.add_node(
                node_id,
                entity_type="item",
                entity_id=item.id,
                name=item.name,
                item_type=item.item_type,
                description=item.description,
                rarity=item.rarity,
                importance=rarity_importance.get(item.rarity, 2.0),
            )
        
        logger.debug(f"Added {len(items)} item nodes")
    
    def _add_location_relationships(self, db):
        """Add edges for NPCs and players at locations."""
        # NPCs at locations
        npcs = db.query(NPC).filter(NPC.world_id == self.world_id).all()
        for npc in npcs:
            if npc.location_id:
                self.graph.add_edge(
                    f"npc_{npc.id}",
                    f"location_{npc.location_id}",
                    relation="located_at",
                    description=f"{npc.name} is at this location",
                    weight=1.0,
                )
        
        # Players at locations
        players = db.query(Player).filter(Player.world_id == self.world_id).all()
        for player in players:
            if player.current_location_id:
                self.graph.add_edge(
                    f"player_{player.id}",
                    f"location_{player.current_location_id}",
                    relation="located_at",
                    description=f"{player.character_name} is at this location",
                    weight=1.0,
                )
    
    def _add_faction_relationships(self, db):
        """Add edges for faction memberships and relations."""
        # NPCs in factions
        npcs = db.query(NPC).filter(
            NPC.world_id == self.world_id,
            NPC.faction_id.isnot(None)
        ).all()
        
        for npc in npcs:
            self.graph.add_edge(
                f"npc_{npc.id}",
                f"faction_{npc.faction_id}",
                relation="member_of",
                description=f"{npc.name} is a member of this faction",
                weight=2.0,
            )
        
        # Faction relations
        factions = db.query(Faction).filter(Faction.world_id == self.world_id).all()
        for faction in factions:
            relations = json.loads(faction.faction_relations or "{}")
            for other_faction_id, relation_type in relations.items():
                if f"faction_{other_faction_id}" in self.entity_index:
                    self.graph.add_edge(
                        f"faction_{faction.id}",
                        f"faction_{other_faction_id}",
                        relation=f"faction_{relation_type}",
                        description=f"Faction relationship: {relation_type}",
                        weight=3.0,
                    )
    
    def _add_npc_relationships(self, db):
        """Add edges for NPC-to-NPC and NPC-to-player relationships."""
        npcs = db.query(NPC).filter(NPC.world_id == self.world_id).all()
        
        for npc in npcs:
            relationships = json.loads(npc.relationships or "{}")
            
            for entity_key, score in relationships.items():
                # Parse entity_key: "player_1" or "npc_2"
                parts = entity_key.split("_")
                if len(parts) != 2:
                    continue
                
                entity_type, entity_id = parts
                target_node = f"{entity_type}_{entity_id}"
                
                if target_node not in self.entity_index:
                    continue
                
                # Determine relation type from score
                if score > 0.5:
                    relation = "loves"
                elif score > 0:
                    relation = "likes"
                elif score < -0.5:
                    relation = "hates"
                elif score < 0:
                    relation = "dislikes"
                else:
                    relation = "neutral_towards"
                
                self.graph.add_edge(
                    f"npc_{npc.id}",
                    target_node,
                    relation=relation,
                    description=f"{npc.name} {relation} this entity",
                    relationship_score=score,
                    weight=abs(score) * 2.0,
                )
    
    def _add_world_events(self, db):
        """Add world events as edges connecting entities."""
        events = db.query(WorldEvent).filter(
            WorldEvent.world_id == self.world_id
        ).order_by(WorldEvent.world_day.asc()).all()
        
        for event in events:
            # Determine source and target nodes
            source_node = None
            target_node = None
            
            if event.player_id:
                source_node = f"player_{event.player_id}"
            elif event.npc_id:
                source_node = f"npc_{event.npc_id}"
            elif event.faction_id:
                source_node = f"faction_{event.faction_id}"
            
            if event.location_id:
                target_node = f"location_{event.location_id}"
            
            # Add event edge
            if source_node and target_node:
                if source_node in self.entity_index and target_node in self.entity_index:
                    self.graph.add_edge(
                        source_node,
                        target_node,
                        relation=event.event_type,
                        description=event.description,
                        title=event.title,
                        world_day=event.world_day,
                        timestamp=event.real_timestamp.isoformat(),
                        importance=event.importance,
                        weight=event.importance,
                    )
        
        logger.debug(f"Added {len(events)} world event edges")
    
    def _add_player_actions(self, db):
        """Add player actions as edges."""
        actions = db.query(PlayerAction).filter(
            PlayerAction.world_id == self.world_id
        ).order_by(PlayerAction.world_day.asc()).all()
        
        for action in actions:
            source_node = f"player_{action.player_id}"
            
            # Determine target based on action
            target_node = None
            if action.target_npc_id:
                target_node = f"npc_{action.target_npc_id}"
            elif action.location_id:
                target_node = f"location_{action.location_id}"
            
            if source_node in self.entity_index and target_node and target_node in self.entity_index:
                self.graph.add_edge(
                    source_node,
                    target_node,
                    relation=action.action_type,
                    description=action.action_detail,
                    world_day=action.world_day,
                    timestamp=action.real_timestamp.isoformat(),
                    outcome=action.outcome,
                    weight=2.0,
                )
        
        logger.debug(f"Added {len(actions)} player action edges")
    
    def _calculate_node_importance(self):
        """
        Calculate importance scores for nodes based on:
        - Number of connections (degree centrality)
        - Number of events involving the node
        - Entity type base importance
        """
        for node in self.graph.nodes():
            # Get current base importance
            base_importance = self.graph.nodes[node].get("importance", 1.0)
            
            # Add importance from connections
            degree = self.graph.degree(node)
            connection_importance = min(degree * 0.5, 5.0)
            
            # Add importance from events
            event_count = sum(
                1 for _, _, data in self.graph.edges(node, data=True)
                if data.get("relation") in ["death", "quest_completed", "faction_action"]
            )
            event_importance = min(event_count * 1.0, 5.0)
            
            # Total importance
            total_importance = base_importance + connection_importance + event_importance
            self.graph.nodes[node]["importance"] = min(total_importance, 10.0)
    
    def get_entity_node(self, entity_type: str, entity_id: int) -> Optional[str]:
        """Get node ID for an entity."""
        node_id = f"{entity_type}_{entity_id}"
        return node_id if node_id in self.entity_index else None
    
    def get_node_data(self, node_id: str) -> Dict:
        """Get all data for a node."""
        if node_id not in self.graph:
            return {}
        return dict(self.graph.nodes[node_id])
    
    def get_neighbors(self, node_id: str, relation_type: Optional[str] = None) -> List[Tuple[str, Dict]]:
        """
        Get all neighbors of a node.
        
        Args:
            node_id: Node to get neighbors for
            relation_type: Optional filter by relation type
            
        Returns:
            List of (neighbor_id, edge_data) tuples
        """
        if node_id not in self.graph:
            return []
        
        neighbors = []
        for neighbor in self.graph.neighbors(node_id):
            # Get all edges between node and neighbor
            edges = self.graph.get_edge_data(node_id, neighbor)
            
            if edges:
                for edge_data in edges.values():
                    if relation_type is None or edge_data.get("relation") == relation_type:
                        neighbors.append((neighbor, edge_data))
        
        return neighbors
    
    def find_path(self, source_node: str, target_node: str, max_hops: int = 3) -> List[List[str]]:
        """
        Find all paths between two nodes up to max_hops.
        
        Args:
            source_node: Starting node
            target_node: Ending node
            max_hops: Maximum path length
            
        Returns:
            List of paths (each path is a list of node IDs)
        """
        if source_node not in self.graph or target_node not in self.graph:
            return []
        
        try:
            # Find all simple paths up to max_hops
            paths = list(nx.all_simple_paths(
                self.graph,
                source_node,
                target_node,
                cutoff=max_hops
            ))
            return paths
        except nx.NetworkXNoPath:
            return []
    
    def get_subgraph(self, center_node: str, radius: int = 2) -> nx.MultiDiGraph:
        """
        Get a subgraph centered on a node.
        
        Args:
            center_node: Center node
            radius: Number of hops to include
            
        Returns:
            Subgraph containing all nodes within radius hops
        """
        if center_node not in self.graph:
            return nx.MultiDiGraph()
        
        # BFS to find all nodes within radius
        nodes_to_include = {center_node}
        current_layer = {center_node}
        
        for _ in range(radius):
            next_layer = set()
            for node in current_layer:
                neighbors = set(self.graph.neighbors(node))
                predecessors = set(self.graph.predecessors(node))
                next_layer.update(neighbors | predecessors)
            
            nodes_to_include.update(next_layer)
            current_layer = next_layer
        
        return self.graph.subgraph(nodes_to_include).copy()
    
    def get_timeline(self, entity_node: str) -> List[Dict]:
        """
        Get chronological timeline of all events involving an entity.
        
        Args:
            entity_node: Entity node ID
            
        Returns:
            List of events sorted by world_day
        """
        if entity_node not in self.graph:
            return []
        
        events = []
        
        # Get all edges involving this node
        for source, target, data in self.graph.edges(entity_node, data=True):
            if "world_day" in data:
                events.append({
                    "source": source,
                    "target": target,
                    "relation": data.get("relation"),
                    "description": data.get("description"),
                    "world_day": data.get("world_day"),
                    "timestamp": data.get("timestamp"),
                })
        
        for source, target, data in self.graph.in_edges(entity_node, data=True):
            if "world_day" in data:
                events.append({
                    "source": source,
                    "target": target,
                    "relation": data.get("relation"),
                    "description": data.get("description"),
                    "world_day": data.get("world_day"),
                    "timestamp": data.get("timestamp"),
                })
        
        # Sort by world_day
        events.sort(key=lambda e: e.get("world_day", 0))
        
        return events
    
    def export_to_dict(self) -> Dict:
        """Export graph to dictionary format for serialization."""
        return {
            "world_id": self.world_id,
            "nodes": [
                {
                    "id": node,
                    **self.graph.nodes[node]
                }
                for node in self.graph.nodes()
            ],
            "edges": [
                {
                    "source": source,
                    "target": target,
                    **data
                }
                for source, target, data in self.graph.edges(data=True)
            ],
            "stats": {
                "total_nodes": self.graph.number_of_nodes(),
                "total_edges": self.graph.number_of_edges(),
            }
        }
