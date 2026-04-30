"""
Quest personalization based on player profile and world state.
Selects appropriate quest type and difficulty for each player.
"""
import json
import random
from typing import Dict, List, Optional
from backend.database.db import SessionLocal, Player, Faction
from backend.database.world_store import (
    get_player, get_factions, get_recent_events,
    get_npcs_at_location, get_location,
)
from backend.narrative.player_profiler import analyze_player_behavior
from backend.prediction.skill_assessor import assess_player_skill
from backend.quest_generator.quest_template import (
    QuestType, QuestDifficulty,
    get_quest_types_for_player,
    get_quest_difficulty_for_skill,
    QUEST_TYPE_CONFIG,
)
from backend.logger import get_logger

logger = get_logger("quest_generator.personalizer")


def select_quest_type_for_player(
    player_id: int,
    world_id: int,
    force_type: Optional[str] = None,
) -> QuestType:
    """
    Selects the most appropriate quest type for a player.
    
    Considers:
    - Player's Bartle type (explorer, achiever, socializer, killer)
    - Recent quest history (avoid repetition)
    - Current world state (wars favor combat quests)
    
    Args:
        player_id: Player ID
        world_id: World ID
        force_type: Optional quest type to force
        
    Returns:
        Selected QuestType
    """
    if force_type:
        try:
            return QuestType(force_type)
        except ValueError:
            logger.warning(f"Invalid quest type: {force_type}")
    
    # Get player profile
    profile = analyze_player_behavior(player_id)
    player_type = profile.get("player_type", "achiever")
    
    # Get suitable quest types
    suitable_types = get_quest_types_for_player(player_type)
    
    if not suitable_types:
        suitable_types = [QuestType.FETCH, QuestType.DELIVER]
    
    # Check recent quest history to avoid repetition
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.id == player_id).first()
        if player:
            quest_log = json.loads(player.quest_log or "{}")
            recent_types = []
            
            # Get types of last 3 quests
            for quest_id, quest_state in list(quest_log.items())[-3:]:
                if isinstance(quest_state, dict):
                    recent_types.append(quest_state.get("type"))
            
            # Filter out recently done types
            filtered_types = [
                qt for qt in suitable_types
                if qt.value not in recent_types
            ]
            
            if filtered_types:
                suitable_types = filtered_types
    finally:
        db.close()
    
    # Weight by world state
    world_events = get_recent_events(world_id, limit=10)
    has_war = any("war" in e.title.lower() for e in world_events)
    has_mystery = any("mysterious" in e.description.lower() for e in world_events)
    
    weights = []
    for quest_type in suitable_types:
        weight = 1.0
        
        # Boost combat quests during war
        if has_war and quest_type in [QuestType.KILL, QuestType.CLEAR, QuestType.DEFEND]:
            weight *= 2.0
        
        # Boost investigation during mysteries
        if has_mystery and quest_type == QuestType.INVESTIGATE:
            weight *= 2.0
        
        weights.append(weight)
    
    # Weighted random selection
    selected = random.choices(suitable_types, weights=weights, k=1)[0]
    
    logger.info(
        f"Quest type selected | player_id={player_id} | "
        f"player_type={player_type} | quest_type={selected.value}"
    )
    
    return selected


def select_quest_difficulty(
    player_id: int,
    world_id: int,
    force_difficulty: Optional[str] = None,
) -> QuestDifficulty:
    """
    Selects appropriate quest difficulty for a player.
    
    Args:
        player_id: Player ID
        world_id: World ID
        force_difficulty: Optional difficulty to force
        
    Returns:
        Selected QuestDifficulty
    """
    if force_difficulty:
        try:
            return QuestDifficulty(force_difficulty)
        except ValueError:
            logger.warning(f"Invalid difficulty: {force_difficulty}")
    
    # Assess player skill
    skill_assessment = assess_player_skill(player_id)
    skill_level = skill_assessment.get("overall_skill", "beginner")
    
    # Get base difficulty
    base_difficulty = get_quest_difficulty_for_skill(skill_level)
    
    # Occasionally offer harder quests for variety
    if random.random() < 0.2:
        difficulty_levels = list(QuestDifficulty)
        current_index = difficulty_levels.index(base_difficulty)
        
        # Move up one level if possible
        if current_index < len(difficulty_levels) - 1:
            base_difficulty = difficulty_levels[current_index + 1]
            logger.info(f"Difficulty increased for variety | player_id={player_id}")
    
    logger.info(
        f"Quest difficulty selected | player_id={player_id} | "
        f"skill={skill_level} | difficulty={base_difficulty.value}"
    )
    
    return base_difficulty


def select_quest_giver(
    world_id: int,
    location_id: int,
    quest_type: QuestType,
    player_id: Optional[int] = None,
) -> Optional[int]:
    """
    Selects an appropriate NPC to give the quest.
    
    Prefers NPCs who:
    - Are at the location
    - Have appropriate role for quest type
    - Have positive or neutral relationship with player
    
    Args:
        world_id: World ID
        location_id: Location where quest originates
        quest_type: Type of quest
        player_id: Optional player ID for relationship check
        
    Returns:
        NPC ID or None
    """
    npcs = get_npcs_at_location(location_id)
    
    if not npcs:
        logger.warning(f"No NPCs at location {location_id} for quest giver")
        return None
    
    # Preferred roles by quest type
    role_preferences = {
        QuestType.FETCH: ["merchant", "noble", "quest_giver"],
        QuestType.DELIVER: ["merchant", "innkeeper", "quest_giver"],
        QuestType.KILL: ["guard", "warrior", "noble", "quest_giver"],
        QuestType.CLEAR: ["guard", "warrior", "quest_giver"],
        QuestType.ESCORT: ["merchant", "noble", "priest", "quest_giver"],
        QuestType.INVESTIGATE: ["guard", "mage", "priest", "quest_giver"],
        QuestType.DIPLOMATIC: ["noble", "priest", "quest_giver"],
        QuestType.CRAFT: ["blacksmith", "merchant", "mage"],
        QuestType.EXPLORE: ["mage", "merchant", "quest_giver"],
        QuestType.RESCUE: ["guard", "noble", "peasant", "quest_giver"],
        QuestType.GATHER: ["merchant", "blacksmith", "mage"],
        QuestType.DEFEND: ["guard", "warrior", "noble"],
    }
    
    preferred_roles = role_preferences.get(quest_type, ["quest_giver"])
    
    # Score each NPC
    scored_npcs = []
    for npc in npcs:
        score = 0.0
        
        # Role match
        if npc.role in preferred_roles:
            score += 10.0
            if npc.role == preferred_roles[0]:
                score += 5.0
        
        # Relationship with player
        if player_id:
            relationships = json.loads(npc.relationships or "{}")
            player_key = f"player_{player_id}"
            relationship_score = relationships.get(player_key, 0.0)
            
            # Prefer neutral or positive relationships
            if relationship_score >= 0:
                score += relationship_score * 5.0
            else:
                score -= abs(relationship_score) * 10.0
        
        # Alive NPCs only
        if not npc.is_alive:
            score = -1000.0
        
        scored_npcs.append((npc.id, score))
    
    # Sort by score
    scored_npcs.sort(key=lambda x: x[1], reverse=True)
    
    if scored_npcs and scored_npcs[0][1] > 0:
        selected_npc_id = scored_npcs[0][0]
        logger.info(
            f"Quest giver selected | npc_id={selected_npc_id} | "
            f"location_id={location_id} | quest_type={quest_type.value}"
        )
        return selected_npc_id
    
    logger.warning(f"No suitable quest giver found at location {location_id}")
    return None


def get_relevant_factions(
    world_id: int,
    player_id: int,
    quest_type: QuestType,
) -> List[Dict]:
    """
    Gets factions relevant to the quest and player.
    
    Returns factions the player has reputation with,
    or factions involved in current world events.
    
    Args:
        world_id: World ID
        player_id: Player ID
        quest_type: Type of quest
        
    Returns:
        List of faction dictionaries with reputation
    """
    db = SessionLocal()
    try:
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            return []
        
        faction_reputation = json.loads(player.faction_reputation or "{}")
        factions = get_factions(world_id)
        
        relevant_factions = []
        for faction in factions:
            faction_key = str(faction.id)
            reputation = faction_reputation.get(faction_key, 0)
            
            # Include factions with non-zero reputation
            if reputation != 0:
                relevant_factions.append({
                    "id": faction.id,
                    "name": faction.name,
                    "type": faction.faction_type,
                    "reputation": reputation,
                })
        
        # If no reputation, include active factions
        if not relevant_factions and factions:
            for faction in factions[:2]:
                relevant_factions.append({
                    "id": faction.id,
                    "name": faction.name,
                    "type": faction.faction_type,
                    "reputation": 0,
                })
        
        return relevant_factions
    
    finally:
        db.close()


def build_quest_context(
    world_id: int,
    player_id: int,
    location_id: int,
    quest_type: QuestType,
    difficulty: QuestDifficulty,
) -> Dict:
    """
    Builds complete context for quest generation.
    
    This context is passed to the LLM to generate
    a personalized quest that fits the world state.
    
    Args:
        world_id: World ID
        player_id: Player ID
        location_id: Starting location
        quest_type: Type of quest
        difficulty: Difficulty level
        
    Returns:
        Context dictionary
    """
    player = get_player(player_id)
    location = get_location(location_id)
    recent_events = get_recent_events(world_id, limit=5)
    relevant_factions = get_relevant_factions(world_id, player_id, quest_type)
    
    context = {
        "world_id": world_id,
        "player": {
            "id": player.id,
            "name": player.character_name,
            "class": player.character_class,
            "level": player.level,
        },
        "location": {
            "id": location.id,
            "name": location.name,
            "type": location.location_type,
            "description": location.description,
        },
        "quest_type": quest_type.value,
        "difficulty": difficulty.value,
        "recent_events": [
            {
                "title": e.title,
                "description": e.description,
            }
            for e in recent_events
        ],
        "relevant_factions": relevant_factions,
    }
    
    return context
