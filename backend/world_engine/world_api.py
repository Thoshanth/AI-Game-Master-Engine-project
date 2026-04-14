import json
from backend.database.world_store import (
    get_world_summary, get_regions, get_locations,
    get_npcs_at_location, get_location, get_npc,
    get_factions, get_recent_events, get_available_quests,
    get_player, get_player_by_username,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.logger import get_logger

logger = get_logger("world_engine.api")


def get_location_context(location_id: int, world_id: int) -> dict:
    """
    Returns complete context for a location —
    everything needed to render a scene for a player.

    Includes: location details, present NPCs,
    available quests, recent events, current time.
    """
    location = get_location(location_id)
    if not location:
        return {}

    world_time = get_current_world_time(world_id)
    npcs = get_npcs_at_location(location_id)
    quests = get_available_quests(world_id, location_id)
    recent_events = get_recent_events(
        world_id, limit=5, location_id=location_id
    )

    return {
        "location": {
            "id": location.id,
            "name": location.name,
            "type": location.location_type,
            "description": location.description,
            "population": location.population,
            "wealth_level": location.wealth_level,
            "safety_level": location.safety_level,
            "current_events": json.loads(
                location.current_events or "[]"
            ),
            "rumors": json.loads(location.rumors or "[]"),
        },
        "world_time": world_time,
        "npcs_present": [
            {
                "id": npc.id,
                "name": npc.name,
                "role": npc.role,
                "appearance": npc.appearance,
                "emotion": npc.emotion_state,
                "current_activity": npc.current_activity,
            }
            for npc in npcs
        ],
        "available_quests": len(quests),
        "recent_events": [
            {
                "title": e.title,
                "description": e.description,
                "world_day": e.world_day,
            }
            for e in recent_events
        ],
    }


def get_npc_context(npc_id: int, player_id: int = None) -> dict:
    """
    Returns complete NPC context for dialogue generation.
    Includes NPC's knowledge of the player if they've met before.
    """
    npc = get_npc(npc_id)
    if not npc:
        return {}

    # Get relationship with this specific player
    relationships = json.loads(npc.relationships or "{}")
    player_relationship = 0.0
    if player_id:
        player_key = f"player_{player_id}"
        player_relationship = relationships.get(player_key, 0.0)

    return {
        "npc": {
            "id": npc.id,
            "name": npc.name,
            "age": npc.age,
            "role": npc.role,
            "appearance": npc.appearance,
            "backstory": npc.backstory,
            "emotion_state": npc.emotion_state,
            "emotion_intensity": npc.emotion_intensity,
            "current_activity": npc.current_activity,
            "personality": {
                "openness": npc.trait_openness,
                "conscientiousness": npc.trait_conscientiousness,
                "extraversion": npc.trait_extraversion,
                "agreeableness": npc.trait_agreeableness,
                "neuroticism": npc.trait_neuroticism,
            },
            "known_rumors": json.loads(npc.known_rumors or "[]"),
        },
        "relationship_with_player": player_relationship,
        "has_met_player": player_id is not None and (
            f"player_{player_id}" in relationships
        ),
    }


def get_player_context(player_id: int, world_id: int) -> dict:
    """
    Returns complete player context.
    """
    player = get_player(player_id)
    if not player:
        return {}

    location = None
    if player.current_location_id:
        location = get_location(player.current_location_id)

    world_time = get_current_world_time(world_id)

    return {
        "player": {
            "id": player.id,
            "username": player.username,
            "character_name": player.character_name,
            "character_class": player.character_class,
            "level": player.level,
            "health": player.health,
            "max_health": player.max_health,
            "gold": player.gold,
            "experience": player.experience,
            "stats": {
                "strength": player.strength,
                "intelligence": player.intelligence,
                "charisma": player.charisma,
                "stealth": player.stealth,
            },
            "inventory": json.loads(player.inventory or "[]"),
            "quest_log": json.loads(player.quest_log or "{}"),
            "faction_reputation": json.loads(
                player.faction_reputation or "{}"
            ),
        },
        "current_location": {
            "id": location.id if location else None,
            "name": location.name if location else "Unknown",
            "type": location.location_type if location else None,
        },
        "world_time": world_time,
    }