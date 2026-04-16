import json
from datetime import datetime
from fastapi import WebSocket
from backend.logger import get_logger

logger = get_logger("multiplayer.connections")


class ConnectionManager:
    """
    Manages all active WebSocket connections.

    Structure:
    connections[world_id][player_id] = WebSocket

    This lets us:
    - Broadcast to all players in a world
    - Send to a specific player
    - Broadcast to players at a specific location
    - Track who is online
    """

    def __init__(self):
        # world_id → {player_id → WebSocket}
        self.connections: dict[int, dict[int, WebSocket]] = {}

        # player_id → current location_id
        self.player_locations: dict[int, int] = {}

        # player_id → connection metadata
        self.player_metadata: dict[int, dict] = {}

        logger.info("ConnectionManager initialized")

    async def connect(
        self,
        websocket: WebSocket,
        world_id: int,
        player_id: int,
        character_name: str = "Unknown",
    ):
        """Accepts and registers a new WebSocket connection."""
        await websocket.accept()

        if world_id not in self.connections:
            self.connections[world_id] = {}

        self.connections[world_id][player_id] = websocket
        self.player_metadata[player_id] = {
            "world_id": world_id,
            "character_name": character_name,
            "connected_at": datetime.utcnow().isoformat(),
            "player_id": player_id,
        }

        logger.info(
            f"Player connected | "
            f"player_id={player_id} | "
            f"world_id={world_id} | "
            f"character='{character_name}'"
        )

        # Notify other players in this world
        await self.broadcast_to_world(
            world_id=world_id,
            message={
                "type": "player_joined",
                "player_id": player_id,
                "character_name": character_name,
                "timestamp": datetime.utcnow().isoformat(),
                "message": (
                    f"{character_name} has entered the world"
                ),
            },
            exclude_player=player_id,
        )

    def disconnect(self, world_id: int, player_id: int):
        """Removes a disconnected player."""
        character_name = self.player_metadata.get(
            player_id, {}
        ).get("character_name", "Unknown")

        if world_id in self.connections:
            self.connections[world_id].pop(player_id, None)
            if not self.connections[world_id]:
                del self.connections[world_id]

        self.player_locations.pop(player_id, None)
        self.player_metadata.pop(player_id, None)

        logger.info(
            f"Player disconnected | "
            f"player_id={player_id} | "
            f"character='{character_name}'"
        )

        return character_name

    async def send_to_player(
        self,
        player_id: int,
        message: dict,
    ) -> bool:
        """Sends a message to a specific player."""
        for world_connections in self.connections.values():
            if player_id in world_connections:
                try:
                    ws = world_connections[player_id]
                    await ws.send_text(json.dumps(message))
                    return True
                except Exception as e:
                    logger.warning(
                        f"Failed to send to player "
                        f"{player_id}: {e}"
                    )
                    return False
        return False

    async def broadcast_to_world(
        self,
        world_id: int,
        message: dict,
        exclude_player: int = None,
    ):
        """Broadcasts a message to all players in a world."""
        world_connections = self.connections.get(world_id, {})
        disconnected = []

        for player_id, ws in world_connections.items():
            if player_id == exclude_player:
                continue
            try:
                await ws.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(
                    f"Broadcast failed for player "
                    f"{player_id}: {e}"
                )
                disconnected.append(player_id)

        # Clean up broken connections
        for player_id in disconnected:
            self.connections[world_id].pop(player_id, None)

        if world_connections:
            logger.debug(
                f"Broadcast to world {world_id} | "
                f"recipients={len(world_connections) - (1 if exclude_player else 0)}"
            )

    async def broadcast_to_location(
        self,
        world_id: int,
        location_id: int,
        message: dict,
        exclude_player: int = None,
    ):
        """Broadcasts to all players at a specific location."""
        world_connections = self.connections.get(world_id, {})
        recipients = 0

        for player_id, ws in world_connections.items():
            if player_id == exclude_player:
                continue
            if self.player_locations.get(player_id) == location_id:
                try:
                    await ws.send_text(json.dumps(message))
                    recipients += 1
                except Exception as e:
                    logger.warning(
                        f"Location broadcast failed: {e}"
                    )

        logger.debug(
            f"Location broadcast | "
            f"location={location_id} | "
            f"recipients={recipients}"
        )

    def update_player_location(
        self,
        player_id: int,
        location_id: int,
    ):
        """Updates tracked location for a player."""
        old_location = self.player_locations.get(player_id)
        self.player_locations[player_id] = location_id

        logger.debug(
            f"Player location updated | "
            f"player_id={player_id} | "
            f"{old_location} → {location_id}"
        )
        return old_location

    def get_online_players(self, world_id: int) -> list[dict]:
        """Returns list of currently connected players."""
        world_connections = self.connections.get(world_id, {})
        online = []
        for player_id in world_connections:
            meta = self.player_metadata.get(player_id, {})
            online.append({
                "player_id": player_id,
                "character_name": meta.get(
                    "character_name", "Unknown"
                ),
                "current_location": self.player_locations.get(
                    player_id
                ),
                "connected_at": meta.get("connected_at"),
            })
        return online

    def get_players_at_location(
        self,
        world_id: int,
        location_id: int,
    ) -> list[dict]:
        """Returns players currently at a specific location."""
        online = self.get_online_players(world_id)
        return [
            p for p in online
            if self.player_locations.get(p["player_id"]) == location_id
        ]

    def is_online(self, player_id: int) -> bool:
        """Checks if a player is currently connected."""
        for world_connections in self.connections.values():
            if player_id in world_connections:
                return True
        return False

    def total_online(self) -> int:
        """Total players online across all worlds."""
        return sum(
            len(connections)
            for connections in self.connections.values()
        )


# Global connection manager — shared across all WebSocket handlers
manager = ConnectionManager()