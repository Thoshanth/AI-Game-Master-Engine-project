"""
Quest type definitions and templates.
Each quest type has specific structure, objectives, and rewards.
"""
import json
from enum import Enum
from typing import Dict, List, Optional
from backend.logger import get_logger

logger = get_logger("quest_generator.template")


class QuestType(str, Enum):
    """All available quest types."""
    FETCH = "fetch"
    DELIVER = "deliver"
    KILL = "kill"
    CLEAR = "clear"
    ESCORT = "escort"
    INVESTIGATE = "investigate"
    DIPLOMATIC = "diplomatic"
    CRAFT = "craft"
    EXPLORE = "explore"
    RESCUE = "rescue"
    GATHER = "gather"
    DEFEND = "defend"


class QuestDifficulty(str, Enum):
    """Quest difficulty levels."""
    TRIVIAL = "trivial"
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    VERY_HARD = "very_hard"
    LEGENDARY = "legendary"


# Quest type configurations
QUEST_TYPE_CONFIG = {
    QuestType.FETCH: {
        "description": "Retrieve a specific item from a location",
        "best_for_player_types": ["achiever", "explorer"],
        "typical_objectives": [
            "Travel to {location}",
            "Find {item}",
            "Return to {quest_giver}",
        ],
        "reward_types": ["gold", "experience", "item", "reputation"],
        "min_difficulty": 1,
        "max_difficulty": 6,
    },
    QuestType.DELIVER: {
        "description": "Transport an item to a specific NPC or location",
        "best_for_player_types": ["achiever", "socializer"],
        "typical_objectives": [
            "Receive {item} from {quest_giver}",
            "Travel to {destination}",
            "Deliver {item} to {recipient}",
        ],
        "reward_types": ["gold", "reputation", "relationship"],
        "min_difficulty": 1,
        "max_difficulty": 5,
    },
    QuestType.KILL: {
        "description": "Eliminate a specific enemy or creature",
        "best_for_player_types": ["killer", "achiever"],
        "typical_objectives": [
            "Locate {target}",
            "Defeat {target}",
            "Report victory to {quest_giver}",
        ],
        "reward_types": ["gold", "experience", "weapon", "reputation"],
        "min_difficulty": 3,
        "max_difficulty": 10,
    },
    QuestType.CLEAR: {
        "description": "Clear a location of all enemies",
        "best_for_player_types": ["killer", "achiever"],
        "typical_objectives": [
            "Travel to {location}",
            "Defeat all enemies in {location}",
            "Report success to {quest_giver}",
        ],
        "reward_types": ["gold", "experience", "loot", "reputation"],
        "min_difficulty": 4,
        "max_difficulty": 10,
    },
    QuestType.ESCORT: {
        "description": "Protect an NPC during a journey",
        "best_for_player_types": ["socializer", "killer"],
        "typical_objectives": [
            "Meet {npc} at {start_location}",
            "Escort {npc} to {destination}",
            "Protect {npc} from threats",
        ],
        "reward_types": ["gold", "reputation", "relationship", "item"],
        "min_difficulty": 3,
        "max_difficulty": 8,
    },
    QuestType.INVESTIGATE: {
        "description": "Uncover information about a mystery",
        "best_for_player_types": ["explorer", "socializer"],
        "typical_objectives": [
            "Gather clues at {location}",
            "Interview {npc_count} witnesses",
            "Discover the truth about {mystery}",
        ],
        "reward_types": ["experience", "lore", "reputation", "secret"],
        "min_difficulty": 2,
        "max_difficulty": 8,
    },
    QuestType.DIPLOMATIC: {
        "description": "Negotiate between factions or NPCs",
        "best_for_player_types": ["socializer", "achiever"],
        "typical_objectives": [
            "Speak with {faction_a} representative",
            "Speak with {faction_b} representative",
            "Broker a deal or truce",
        ],
        "reward_types": ["reputation", "gold", "influence", "relationship"],
        "min_difficulty": 4,
        "max_difficulty": 9,
    },
    QuestType.CRAFT: {
        "description": "Create a specific item",
        "best_for_player_types": ["achiever", "explorer"],
        "typical_objectives": [
            "Gather {material_count} materials",
            "Find crafting location",
            "Craft {item}",
        ],
        "reward_types": ["item", "experience", "reputation"],
        "min_difficulty": 2,
        "max_difficulty": 7,
    },
    QuestType.EXPLORE: {
        "description": "Discover and map a new location",
        "best_for_player_types": ["explorer", "achiever"],
        "typical_objectives": [
            "Travel to {region}",
            "Discover {location}",
            "Document findings",
        ],
        "reward_types": ["experience", "lore", "map", "discovery"],
        "min_difficulty": 2,
        "max_difficulty": 8,
    },
    QuestType.RESCUE: {
        "description": "Save a captured or endangered NPC",
        "best_for_player_types": ["killer", "socializer", "achiever"],
        "typical_objectives": [
            "Locate {npc} at {location}",
            "Defeat captors or overcome danger",
            "Escort {npc} to safety",
        ],
        "reward_types": ["gold", "experience", "relationship", "reputation"],
        "min_difficulty": 4,
        "max_difficulty": 9,
    },
    QuestType.GATHER: {
        "description": "Collect multiple items or resources",
        "best_for_player_types": ["achiever", "explorer"],
        "typical_objectives": [
            "Collect {quantity} {item_type}",
            "Search {location_count} locations",
            "Return items to {quest_giver}",
        ],
        "reward_types": ["gold", "experience", "item"],
        "min_difficulty": 1,
        "max_difficulty": 6,
    },
    QuestType.DEFEND: {
        "description": "Protect a location from attack",
        "best_for_player_types": ["killer", "achiever"],
        "typical_objectives": [
            "Prepare defenses at {location}",
            "Survive {wave_count} waves of enemies",
            "Ensure {location} survives",
        ],
        "reward_types": ["gold", "experience", "reputation", "weapon"],
        "min_difficulty": 5,
        "max_difficulty": 10,
    },
}


def get_quest_types_for_player(player_type: str) -> List[QuestType]:
    """
    Returns quest types best suited for a player's Bartle type.
    
    Args:
        player_type: explorer, achiever, socializer, or killer
        
    Returns:
        List of QuestType enums sorted by suitability
    """
    primary_types = []
    secondary_types = []
    
    for quest_type, config in QUEST_TYPE_CONFIG.items():
        if player_type in config["best_for_player_types"]:
            if config["best_for_player_types"][0] == player_type:
                primary_types.append(quest_type)
            else:
                secondary_types.append(quest_type)
    
    return primary_types + secondary_types


def get_quest_difficulty_for_skill(skill_level: str) -> QuestDifficulty:
    """
    Maps player skill level to appropriate quest difficulty.
    
    Args:
        skill_level: novice, beginner, intermediate, advanced, expert
        
    Returns:
        QuestDifficulty enum
    """
    difficulty_map = {
        "novice": QuestDifficulty.TRIVIAL,
        "beginner": QuestDifficulty.EASY,
        "intermediate": QuestDifficulty.MODERATE,
        "advanced": QuestDifficulty.HARD,
        "expert": QuestDifficulty.VERY_HARD,
    }
    return difficulty_map.get(skill_level, QuestDifficulty.MODERATE)


def get_difficulty_multipliers(difficulty: QuestDifficulty) -> Dict:
    """
    Returns reward and challenge multipliers for a difficulty level.
    
    Args:
        difficulty: Quest difficulty level
        
    Returns:
        Dict with gold_multiplier, xp_multiplier, danger_level
    """
    multipliers = {
        QuestDifficulty.TRIVIAL: {
            "gold_multiplier": 0.5,
            "xp_multiplier": 0.5,
            "danger_level": 1,
            "time_pressure": False,
        },
        QuestDifficulty.EASY: {
            "gold_multiplier": 1.0,
            "xp_multiplier": 1.0,
            "danger_level": 2,
            "time_pressure": False,
        },
        QuestDifficulty.MODERATE: {
            "gold_multiplier": 1.5,
            "xp_multiplier": 1.5,
            "danger_level": 4,
            "time_pressure": False,
        },
        QuestDifficulty.HARD: {
            "gold_multiplier": 2.5,
            "xp_multiplier": 2.5,
            "danger_level": 6,
            "time_pressure": True,
        },
        QuestDifficulty.VERY_HARD: {
            "gold_multiplier": 4.0,
            "xp_multiplier": 4.0,
            "danger_level": 8,
            "time_pressure": True,
        },
        QuestDifficulty.LEGENDARY: {
            "gold_multiplier": 10.0,
            "xp_multiplier": 10.0,
            "danger_level": 10,
            "time_pressure": True,
        },
    }
    return multipliers.get(difficulty, multipliers[QuestDifficulty.MODERATE])


def validate_quest_structure(quest_data: Dict) -> bool:
    """
    Validates that a quest has all required fields.
    
    Args:
        quest_data: Quest dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = [
        "title", "description", "quest_type", "objectives",
        "rewards", "difficulty"
    ]
    
    for field in required_fields:
        if field not in quest_data:
            logger.error(f"Quest missing required field: {field}")
            return False
    
    if not quest_data.get("objectives"):
        logger.error("Quest has no objectives")
        return False
    
    if not quest_data.get("rewards"):
        logger.error("Quest has no rewards")
        return False
    
    return True


def create_quest_template(
    quest_type: QuestType,
    difficulty: QuestDifficulty,
) -> Dict:
    """
    Creates a basic quest template with placeholders.
    
    Args:
        quest_type: Type of quest
        difficulty: Difficulty level
        
    Returns:
        Quest template dictionary
    """
    config = QUEST_TYPE_CONFIG[quest_type]
    multipliers = get_difficulty_multipliers(difficulty)
    
    base_gold = 50
    base_xp = 100
    
    template = {
        "quest_type": quest_type.value,
        "difficulty": difficulty.value,
        "title": f"[{quest_type.value.title()}] Quest",
        "description": config["description"],
        "objectives": config["typical_objectives"].copy(),
        "rewards": {
            "gold": int(base_gold * multipliers["gold_multiplier"]),
            "experience": int(base_xp * multipliers["xp_multiplier"]),
            "reputation_changes": {},
        },
        "danger_level": multipliers["danger_level"],
        "has_time_pressure": multipliers["time_pressure"],
        "expires_in_days": 7.0 if multipliers["time_pressure"] else None,
        "state": "hidden",
        "trigger_conditions": {},
    }
    
    return template
