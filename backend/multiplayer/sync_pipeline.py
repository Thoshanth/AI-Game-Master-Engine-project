import json
from datetime import datetime
from backend.multiplayer.connection_manager import manager
from backend.multiplayer.event_broadcaster import (
    broadcast_player_action,
    broadcast_npc_state_change,
    broadcast_consequence,
    broadcast_chat,
)
from backend.multiplayer.world_sync import (
    build_world_snapshot,
    sync_player_move,
)
from backend.database.world_store import get_player
from backend.logger import get_logger

logger = get_logger("multiplayer.pipeline")


async def handle_incoming_message(
    world_id: int,
    player_id: int,
    raw_message: str,
) -> dict:
    """
    Processes incoming WebSocket messages from players.

    Message format:
    {
        "action": "move|chat|action|ping",
        "data": {...}
    }

    Routes to appropriate handler and returns response.
    """
    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON message"}

    action = message.get("action", "")
    data = message.get("data", {})

    logger.debug(
        f"Incoming message | "
        f"player={player_id} | action={action}"
    )

    if action == "ping":
        return {
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat(),
        }

    elif action == "move":
        new_location_id = data.get("location_id")
        if not new_location_id:
            return {"error": "location_id required"}

        result = await sync_player_move(
            world_id=world_id,
            player_id=player_id,
            new_location_id=new_location_id,
        )
        return {"type": "move_result", "data": result}

    elif action == "chat":
        message_text = data.get("message", "")
        if not message_text:
            return {"error": "message required"}

        player = get_player(player_id)
        character_name = (
            player.character_name if player else "Unknown"
        )

        await broadcast_chat(
            world_id=world_id,
            player_id=player_id,
            character_name=character_name,
            message=message_text,
            location_id=manager.player_locations.get(player_id),
            chat_scope=data.get("scope", "location"),
        )
        return {"type": "chat_sent"}

    elif action == "action":
        action_type = data.get("action_type", "unknown")
        description = data.get("description", "")
        is_notable = data.get("notable", False)

        player = get_player(player_id)
        character_name = (
            player.character_name if player else "Unknown"
        )

        await broadcast_player_action(
            world_id=world_id,
            player_id=player_id,
            character_name=character_name,
            action_type=action_type,
            action_description=description,
            location_id=manager.player_locations.get(player_id),
            is_notable=is_notable,
        )
        return {"type": "action_broadcast"}

    elif action == "get_snapshot":
        snapshot = await build_world_snapshot(world_id, player_id)
        return snapshot

    else:
        return {
            "error": f"Unknown action: {action}",
            "valid_actions": [
                "ping", "move", "chat",
                "action", "get_snapshot"
            ],
        }