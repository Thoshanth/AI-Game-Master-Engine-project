"""
Quest chain management and progression.
Handles quest dependencies, unlocking, and branching paths.
"""
import json
from typing import Dict, List, Optional
from backend.database.db import SessionLocal, Quest, Player, QuestState
from backend.database.world_store import get_player
from backend.logger import get_logger

logger = get_logger("quest_generator.chain")


class QuestChain:
    """
    Manages a chain of connected quests.
    
    Quest chains have:
    - Linear progression (quest 1 → 2 → 3)
    - Branching based on completion method
    - Shared narrative thread
    - Escalating difficulty
    """
    
    def __init__(self, chain_id: str, world_id: int):
        self.chain_id = chain_id
        self.world_id = world_id
        self.quests: List[Dict] = []
        self.current_position = 0
    
    def add_quest(self, quest_data: Dict, position: int):
        """Add a quest to the chain at a specific position."""
        quest_data["chain_id"] = self.chain_id
        quest_data["chain_position"] = position
        self.quests.append(quest_data)
    
    def get_next_quest(self, player_id: int) -> Optional[Dict]:
        """
        Gets the next quest in the chain for a player.
        
        Returns None if:
        - Chain is complete
        - Previous quest not completed
        - Player doesn't meet requirements
        """
        player = get_player(player_id)
        if not player:
            return None
        
        quest_log = json.loads(player.quest_log or "{}")
        
        # Find current position in chain
        for quest in self.quests:
            quest_id = str(quest.get("id"))
            quest_state = quest_log.get(quest_id, {})
            
            # If quest is active or available, this is current position
            if quest_state.get("state") in ["active", "available"]:
                return quest
            
            # If quest is completed, check next
            if quest_state.get("state") == "completed":
                continue
            
            # If quest is not in log, this is the next one
            if quest_id not in quest_log:
                # Check if previous quest is completed
                if quest.get("chain_position", 0) > 1:
                    prev_quest = self._get_quest_at_position(
                        quest["chain_position"] - 1
                    )
                    if prev_quest:
                        prev_id = str(prev_quest.get("id"))
                        prev_state = quest_log.get(prev_id, {})
                        if prev_state.get("state") != "completed":
                            return None
                
                return quest
        
        return None
    
    def _get_quest_at_position(self, position: int) -> Optional[Dict]:
        """Gets quest at a specific chain position."""
        for quest in self.quests:
            if quest.get("chain_position") == position:
                return quest
        return None
    
    def get_chain_progress(self, player_id: int) -> Dict:
        """
        Gets player's progress through the chain.
        
        Returns:
            Dict with completed, current, remaining counts
        """
        player = get_player(player_id)
        if not player:
            return {}
        
        quest_log = json.loads(player.quest_log or "{}")
        
        completed = 0
        current = None
        remaining = 0
        
        for quest in sorted(self.quests, key=lambda q: q.get("chain_position", 0)):
            quest_id = str(quest.get("id"))
            quest_state = quest_log.get(quest_id, {})
            
            if quest_state.get("state") == "completed":
                completed += 1
            elif quest_state.get("state") in ["active", "available"]:
                current = quest
            else:
                remaining += 1
        
        return {
            "chain_id": self.chain_id,
            "total_quests": len(self.quests),
            "completed": completed,
            "current_quest": current.get("title") if current else None,
            "remaining": remaining,
            "progress_percentage": (completed / len(self.quests) * 100) if self.quests else 0,
        }


def create_branching_chain(
    base_quest: Dict,
    branch_count: int = 2,
) -> List[List[Dict]]:
    """
    Creates a branching quest chain.
    
    Structure:
    Quest 1 (base)
      ├─> Branch A: Quest 2A → Quest 3A
      └─> Branch B: Quest 2B → Quest 3B
    
    Branch selection based on how Quest 1 was completed.
    
    Args:
        base_quest: Starting quest
        branch_count: Number of branches (2-3)
        
    Returns:
        List of quest chains (one per branch)
    """
    logger.info(f"Creating branching chain | branches={branch_count}")
    
    branches = []
    
    # Define branch themes
    branch_themes = [
        {"name": "honorable", "description": "Completed with honor and mercy"},
        {"name": "ruthless", "description": "Completed with violence and force"},
        {"name": "cunning", "description": "Completed with deception and stealth"},
    ]
    
    for i in range(min(branch_count, len(branch_themes))):
        theme = branch_themes[i]
        branch = [base_quest.copy()]
        
        # Mark base quest with branch unlock conditions
        branch[0]["unlocks_branches"] = [
            {
                "branch_id": theme["name"],
                "condition": theme["description"],
            }
        ]
        
        branches.append(branch)
    
    return branches


def check_quest_unlock_conditions(
    quest: Dict,
    player_id: int,
    world_id: int,
) -> bool:
    """
    Checks if a player meets the conditions to unlock a quest.
    
    Conditions can include:
    - Previous quest completed
    - Faction reputation threshold
    - Player level requirement
    - World state requirements
    
    Args:
        quest: Quest dictionary
        player_id: Player ID
        world_id: World ID
        
    Returns:
        True if conditions met, False otherwise
    """
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return False
        
        trigger_conditions = quest.get("trigger_conditions", {})
        
        # Check level requirement
        min_level = trigger_conditions.get("min_level", 0)
        if player.level < min_level:
            logger.debug(
                f"Quest locked | player level {player.level} < {min_level}"
            )
            return False
        
        # Check faction reputation
        faction_requirements = trigger_conditions.get("faction_reputation", {})
        if faction_requirements:
            player_reputation = json.loads(player.faction_reputation or "{}")
            
            for faction_id, required_rep in faction_requirements.items():
                current_rep = player_reputation.get(str(faction_id), 0)
                if current_rep < required_rep:
                    logger.debug(
                        f"Quest locked | faction {faction_id} "
                        f"reputation {current_rep} < {required_rep}"
                    )
                    return False
        
        # Check prerequisite quests
        prerequisite_quests = trigger_conditions.get("prerequisite_quests", [])
        if prerequisite_quests:
            quest_log = json.loads(player.quest_log or "{}")
            
            for prereq_id in prerequisite_quests:
                prereq_state = quest_log.get(str(prereq_id), {})
                if prereq_state.get("state") != "completed":
                    logger.debug(
                        f"Quest locked | prerequisite quest {prereq_id} "
                        f"not completed"
                    )
                    return False
        
        # Check world state conditions
        world_conditions = trigger_conditions.get("world_state", {})
        if world_conditions:
            # Example: {"faction_1_at_war": True}
            # This would require checking world events
            pass
        
        return True
    
    finally:
        db.close()


def get_quest_chain_recommendations(
    player_id: int,
    world_id: int,
) -> List[Dict]:
    """
    Recommends quest chains for a player based on their profile.
    
    Args:
        player_id: Player ID
        world_id: World ID
        
    Returns:
        List of recommended quest chain summaries
    """
    # This would integrate with the narrative engine
    # to find active story arcs and convert them to quest chains
    
    recommendations = []
    
    # Example recommendation structure
    example = {
        "chain_id": "shadow_conspiracy_1",
        "title": "The Shadow Conspiracy",
        "description": "Uncover a plot against the kingdom",
        "quest_count": 5,
        "estimated_difficulty": "hard",
        "estimated_duration": "3-5 hours",
        "rewards_preview": {
            "total_gold": 500,
            "total_xp": 2000,
            "unique_items": 2,
        },
    }
    
    return recommendations


def adapt_quest_chain_to_choices(
    chain_id: str,
    player_id: int,
    completed_quest_id: int,
    completion_method: str,
) -> Optional[Dict]:
    """
    Adapts the next quest in a chain based on how the previous was completed.
    
    Args:
        chain_id: Quest chain ID
        player_id: Player ID
        completed_quest_id: ID of just-completed quest
        completion_method: How it was completed (combat, stealth, diplomatic, etc.)
        
    Returns:
        Modified next quest, or None if chain ends
    """
    logger.info(
        f"Adapting chain | chain={chain_id} | "
        f"method={completion_method}"
    )
    
    # This would modify the next quest's objectives and dialogue
    # based on the player's approach to the previous quest
    
    adaptations = {
        "combat": {
            "reputation_modifier": {"military": +10, "peaceful": -5},
            "next_quest_hint": "Your violent approach has been noted",
        },
        "stealth": {
            "reputation_modifier": {"thieves": +10},
            "next_quest_hint": "Your subtlety impressed the right people",
        },
        "diplomatic": {
            "reputation_modifier": {"nobles": +10, "merchants": +5},
            "next_quest_hint": "Your silver tongue opens new doors",
        },
    }
    
    adaptation = adaptations.get(completion_method, {})
    
    return {
        "completion_method": completion_method,
        "reputation_changes": adaptation.get("reputation_modifier", {}),
        "narrative_consequence": adaptation.get("next_quest_hint", ""),
    }
