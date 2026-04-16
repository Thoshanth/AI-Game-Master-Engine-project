import json
from datetime import datetime
from backend.multiplayer.connection_manager import manager
from backend.logger import get_logger

logger = get_logger("multiplayer.broadcaster")

# Event type definitions for type safety
class EventTypes:
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    PLAYER_MOVED = "player_moved"
    PLAYER_ACTION = "player_action"
    NPC_STATE_CHANGED = "npc_state_changed"
    WORLD_EVENT = "world_event"
    FACTION_UPDATE = "faction_update"
    CONSEQUENCE_UPDATE = "consequence_update"
    CHAT_MESSAGE = "chat_message"
    WORLD_SNAPSHOT = "world_snapshot"
    LOCATION_UPDATE = "location_update"
    QUEST_UPDATE = "quest_update"
    EMERGENCY_ALERT = "emergency_alert"


def build_event(
    event_type: str,
    data: dict,
    player_id: int = None,
    location_id: int = None,
    importance: str = "normal",
) -> dict:
    """Builds a standardized event message."""
    return {
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "player_id": player_id,
        "location_id": location_id,
        "importance": importance,
        "data": data,
    }


async def broadcast_player_moved(
    world_id: int,
    player_id: int,
    character_name: str,
    from_location: dict,
    to_location: dict,
):
    """Broadcasts player movement to all relevant players."""
    # Update location tracking
    old_location_id = manager.update_player_location(
        player_id, to_location.get("id")
    )

    # Notify players at old location
    if old_location_id:
        await manager.broadcast_to_location(
            world_id=world_id,
            location_id=old_location_id,
            message=build_event(
                EventTypes.PLAYER_MOVED,
                {
                    "character_name": character_name,
                    "departed_to": to_location.get("name"),
                    "message": (
                        f"{character_name} has left for "
                        f"{to_location.get('name', 'unknown')}"
                    ),
                },
                player_id=player_id,
                location_id=old_location_id,
            ),
            exclude_player=player_id,
        )

    # Notify players at new location
    await manager.broadcast_to_location(
        world_id=world_id,
        location_id=to_location.get("id"),
        message=build_event(
            EventTypes.PLAYER_MOVED,
            {
                "character_name": character_name,
                "arrived_from": from_location.get("name", "somewhere"),
                "message": (
                    f"{character_name} has arrived from "
                    f"{from_location.get('name', 'unknown')}"
                ),
            },
            player_id=player_id,
            location_id=to_location.get("id"),
        ),
        exclude_player=player_id,
    )

    logger.info(
        f"Player movement broadcast | "
        f"player={player_id} | "
        f"{from_location.get('name')} → {to_location.get('name')}"
    )


async def broadcast_player_action(
    world_id: int,
    player_id: int,
    character_name: str,
    action_type: str,
    action_description: str,
    location_id: int = None,
    is_notable: bool = False,
):
    """Broadcasts a player action to relevant observers."""
    event = build_event(
        EventTypes.PLAYER_ACTION,
        {
            "character_name": character_name,
            "action_type": action_type,
            "description": action_description,
            "notable": is_notable,
        },
        player_id=player_id,
        location_id=location_id,
        importance="high" if is_notable else "normal",
    )

    if is_notable:
        # Notable actions broadcast world-wide
        await manager.broadcast_to_world(
            world_id=world_id,
            message=event,
            exclude_player=player_id,
        )
    elif location_id:
        # Regular actions only to same location
        await manager.broadcast_to_location(
            world_id=world_id,
            location_id=location_id,
            message=event,
            exclude_player=player_id,
        )


async def broadcast_npc_state_change(
    world_id: int,
    npc_id: int,
    npc_name: str,
    location_id: int,
    change_type: str,
    new_state: dict,
):
    """Broadcasts NPC state change to players at same location."""
    await manager.broadcast_to_location(
        world_id=world_id,
        location_id=location_id,
        message=build_event(
            EventTypes.NPC_STATE_CHANGED,
            {
                "npc_id": npc_id,
                "npc_name": npc_name,
                "change_type": change_type,
                "new_state": new_state,
                "message": _npc_change_message(
                    npc_name, change_type, new_state
                ),
            },
            location_id=location_id,
        ),
    )

    logger.debug(
        f"NPC state broadcast | "
        f"npc={npc_name} | change={change_type}"
    )


async def broadcast_world_event(
    world_id: int,
    event_title: str,
    event_description: str,
    severity: str = "moderate",
    location_id: int = None,
):
    """Broadcasts a world event to all players."""
    importance = (
        "critical" if severity == "catastrophic"
        else "high" if severity == "major"
        else "normal"
    )

    event = build_event(
        EventTypes.WORLD_EVENT,
        {
            "title": event_title,
            "description": event_description,
            "severity": severity,
        },
        location_id=location_id,
        importance=importance,
    )

    if location_id:
        await manager.broadcast_to_location(
            world_id=world_id,
            location_id=location_id,
            message=event,
        )
    else:
        await manager.broadcast_to_world(
            world_id=world_id,
            message=event,
        )

    logger.info(
        f"World event broadcast | "
        f"title='{event_title}' | severity={severity}"
    )


async def broadcast_consequence(
    world_id: int,
    player_id: int,
    consequence_summary: str,
    affected_players: list[int] = None,
):
    """
    Broadcasts that a player's action caused consequences.
    All affected players receive notification.
    """
    event = build_event(
        EventTypes.CONSEQUENCE_UPDATE,
        {
            "consequence": consequence_summary,
            "caused_by_player": player_id,
        },
        player_id=player_id,
        importance="high",
    )

    if affected_players:
        for affected_id in affected_players:
            await manager.send_to_player(affected_id, event)
    else:
        await manager.broadcast_to_world(
            world_id=world_id,
            message=event,
            exclude_player=player_id,
        )


async def broadcast_chat(
    world_id: int,
    player_id: int,
    character_name: str,
    message: str,
    location_id: int = None,
    chat_scope: str = "location",
):
    """
    Broadcasts a player chat message.
    scope: location (only nearby) or world (everyone)
    """
    event = build_event(
        EventTypes.CHAT_MESSAGE,
        {
            "character_name": character_name,
            "message": message,
            "scope": chat_scope,
        },
        player_id=player_id,
        location_id=location_id,
    )

    if chat_scope == "world":
        await manager.broadcast_to_world(
            world_id=world_id,
            message=event,
            exclude_player=player_id,
        )
    elif location_id:
        await manager.broadcast_to_location(
            world_id=world_id,
            location_id=location_id,
            message=event,
            exclude_player=player_id,
        )


def _npc_change_message(
    npc_name: str,
    change_type: str,
    new_state: dict,
) -> str:
    messages = {
        "emotion_changed": (
            f"{npc_name}'s demeanor shifts — "
            f"they appear {new_state.get('emotion', 'different')}"
        ),
        "location_changed": (
            f"{npc_name} has moved to a different area"
        ),
        "died": (
            f"{npc_name} has died"
        ),
        "quest_given": (
            f"{npc_name} is offering a new quest"
        ),
    }
    return messages.get(
        change_type,
        f"{npc_name} has changed"
    )