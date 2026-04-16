import json
from backend.database.world_store import (
    get_world_summary, get_recent_events,
    get_available_quests, get_player,
    get_location, move_player,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.world_engine.world_api import get_location_context
from backend.multiplayer.connection_manager import manager
from backend.multiplayer.event_broadcaster import (
    broadcast_player_moved,
    broadcast_world_event,
)
from backend.logger import get_logger

logger = get_logger("multiplayer.sync")


async def build_world_snapshot(
    world_id: int,
    player_id: int,
) -> dict:
    """
    Builds the initial world state snapshot sent to a
    player when they first connect.

    Includes everything they need to know immediately:
    current time, location, nearby NPCs, online players,
    recent events, active quests.
    """
    logger.info(
        f"Building snapshot | "
        f"world={world_id} | player={player_id}"
    )

    world_summary = get_world_summary(world_id)
    world_time = get_current_world_time(world_id)
    player = get_player(player_id)

    # Get player's current location context
    location_context = {}
    if player and player.current_location_id:
        location_context = get_location_context(
            player.current_location_id, world_id
        )

    # Recent notable events
    recent_events = get_recent_events(
        world_id, limit=5, notable_only=True
    )

    # Online players
    online_players = manager.get_online_players(world_id)

    # Active quests at location
    quests = []
    if player and player.current_location_id:
        quests = get_available_quests(
            world_id, player.current_location_id
        )

    snapshot = {
        "type": "world_snapshot",
        "world": {
            "id": world_id,
            "name": world_summary.get("name", "Unknown"),
            "current_time": world_time,
        },
        "your_character": {
            "player_id": player_id,
            "name": player.character_name if player else "Unknown",
            "class": player.character_class if player else "Unknown",
            "level": player.level if player else 1,
            "health": player.health if player else 100,
            "gold": player.gold if player else 0,
        },
        "current_location": location_context,
        "online_players": online_players,
        "recent_world_events": [
            {
                "title": e.title,
                "description": e.description[:100],
                "world_day": e.world_day,
            }
            for e in recent_events
        ],
        "available_quests": len(quests),
        "world_statistics": world_summary.get("statistics", {}),
    }

    logger.info(
        f"Snapshot built | "
        f"online_players={len(online_players)} | "
        f"recent_events={len(recent_events)}"
    )

    return snapshot


async def sync_player_move(
    world_id: int,
    player_id: int,
    new_location_id: int,
) -> dict:
    """
    Handles a player moving to a new location.

    1. Gets current location (for departure message)
    2. Updates player location in database
    3. Updates location tracking in manager
    4. Broadcasts movement to all affected players
    5. Returns new location context

    This is the core of real-time multiplayer sync.
    """
    player = get_player(player_id)
    if not player:
        return {"error": "Player not found"}

    old_location_id = player.current_location_id
    old_location = {}
    if old_location_id:
        old_loc = get_location(old_location_id)
        if old_loc:
            old_location = {
                "id": old_loc.id,
                "name": old_loc.name,
            }

    new_loc = get_location(new_location_id)
    if not new_loc:
        return {"error": "Destination not found"}

    new_location = {
        "id": new_loc.id,
        "name": new_loc.name,
        "type": new_loc.location_type,
    }

    # Update database
    move_player(player_id, new_location_id)

    # Broadcast movement
    await broadcast_player_moved(
        world_id=world_id,
        player_id=player_id,
        character_name=player.character_name,
        from_location=old_location,
        to_location=new_location,
    )

    # Get new location context
    location_context = get_location_context(
        new_location_id, world_id
    )

    logger.info(
        f"Player moved | player={player_id} | "
        f"{old_location.get('name', 'unknown')} → "
        f"{new_location.get('name')}"
    )

    return {
        "moved_to": new_location,
        "location_context": location_context,
        "players_here": manager.get_players_at_location(
            world_id, new_location_id
        ),
    }


async def sync_world_event_to_all(
    world_id: int,
    event_title: str,
    event_description: str,
    severity: str = "moderate",
):
    """
    Broadcasts a world event to all connected players.
    Called by the narrative engine when major events occur.
    """
    await broadcast_world_event(
        world_id=world_id,
        event_title=event_title,
        event_description=event_description,
        severity=severity,
    )