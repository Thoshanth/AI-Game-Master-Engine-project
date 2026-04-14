import json
import time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from backend.database.db import init_db
from backend.database.world_store import (
    get_world_summary, get_all_worlds,
    get_regions, get_locations, get_npcs_at_location,
    get_factions, get_recent_events, get_available_quests,
    create_player, get_player_by_username,
    record_event, update_npc_emotion,
    move_player, update_player_stats,
    record_player_action,
)
from backend.world_engine.world_builder import build_complete_world
from backend.world_engine.world_clock import get_current_world_time
from backend.world_engine.world_api import (
    get_location_context, get_npc_context, get_player_context
)
from backend.logger import get_logger

logger = get_logger("main")

Path("game_data").mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("AI Game Master Engine starting")
    logger.info("=" * 60)
    init_db()
    logger.info("World state database initialized")
    yield
    logger.info("AI Game Master Engine shutting down")


app = FastAPI(
    title="AI Game Master Engine",
    version="0.1.0",
    docs_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="AI Game Master Engine",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )


# ══════════════════════════════════════════════════════════════════
# STAGE 1 — World State Engine
# ══════════════════════════════════════════════════════════════════

@app.post("/world/create", tags=["Stage 1 - World State"])
def create_world_endpoint(
    name: str,
    theme: str = "dark fantasy",
):
    """
    Creates a complete game world using LLM-generated content.

    Generates:
    - World concept and description
    - 4 geographic regions with terrain and resources
    - Starting city + tavern + market + dungeon
    - 3 factions with goals and relationships
    - 6 NPCs with personalities, backstories, and secrets
    - 2 starting quests
    - World history event log begins

    theme: dark fantasy, steampunk, post-apocalyptic,
           space opera, mythological, pirate, etc.
    """
    logger.info(f"World creation | name='{name}' | theme='{theme}'")
    try:
        result = build_complete_world(name, theme)
        return result
    except Exception as e:
        logger.error(f"World creation failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.get("/world/{world_id}", tags=["Stage 1 - World State"])
def get_world_endpoint(world_id: int):
    """Get complete world summary with statistics."""
    summary = get_world_summary(world_id)
    if not summary:
        raise HTTPException(404, f"World {world_id} not found")
    return summary


@app.get("/worlds", tags=["Stage 1 - World State"])
def list_worlds():
    """List all created worlds."""
    worlds = get_all_worlds()
    return [
        {
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "created_at": w.created_at.isoformat(),
        }
        for w in worlds
    ]


@app.get("/world/{world_id}/time", tags=["Stage 1 - World State"])
def get_world_time(world_id: int):
    """
    Get current world time.
    Time passes automatically based on real elapsed time.
    """
    world_time = get_current_world_time(world_id)
    if not world_time:
        raise HTTPException(404, f"World {world_id} not found")
    return world_time


@app.get("/world/{world_id}/regions", tags=["Stage 1 - World State"])
def get_world_regions(world_id: int):
    """Get all regions in a world."""
    regions = get_regions(world_id)
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "terrain_type": r.terrain_type,
            "danger_level": r.danger_level,
            "map_x": r.map_x,
            "map_y": r.map_y,
            "resources": json.loads(r.resources or "[]"),
        }
        for r in regions
    ]


@app.get("/world/{world_id}/factions", tags=["Stage 1 - World State"])
def get_world_factions(world_id: int):
    """Get all active factions in a world."""
    factions = get_factions(world_id)
    return [
        {
            "id": f.id,
            "name": f.name,
            "type": f.faction_type,
            "description": f.description,
            "motto": f.motto,
            "wealth": f.wealth,
            "military_strength": f.military_strength,
            "goals": json.loads(f.current_goals or "[]"),
        }
        for f in factions
    ]


@app.get("/world/{world_id}/events", tags=["Stage 1 - World State"])
def get_world_events(
    world_id: int,
    limit: int = 20,
    notable_only: bool = False,
):
    """Get world event history."""
    events = get_recent_events(
        world_id, limit=limit, notable_only=notable_only
    )
    return [
        {
            "id": e.id,
            "type": e.event_type,
            "title": e.title,
            "description": e.description,
            "world_day": e.world_day,
            "importance": e.importance,
            "is_notable": e.is_notable,
            "timestamp": e.real_timestamp.isoformat(),
        }
        for e in events
    ]


@app.get("/location/{location_id}/context", tags=["Stage 1 - World State"])
def get_location_context_endpoint(
    location_id: int,
    world_id: int,
    player_id: int = None,
):
    """
    Get complete scene context for a location.
    Returns everything needed to describe the scene to a player.
    """
    context = get_location_context(location_id, world_id)
    if not context:
        raise HTTPException(404, f"Location {location_id} not found")
    return context


@app.get("/npc/{npc_id}/context", tags=["Stage 1 - World State"])
def get_npc_context_endpoint(npc_id: int, player_id: int = None):
    """Get complete NPC context for dialogue generation."""
    context = get_npc_context(npc_id, player_id)
    if not context:
        raise HTTPException(404, f"NPC {npc_id} not found")
    return context


@app.post("/player/create", tags=["Stage 1 - World State"])
def create_player_endpoint(
    world_id: int,
    username: str,
    character_name: str,
    character_class: str = "adventurer",
):
    """
    Creates a new player in the world.
    Player starts at the world's starting city.
    """
    logger.info(f"Player creation | username='{username}'")
    try:
        # Get starting location (first location in first region)
        regions = get_regions(world_id)
        starting_location_id = None
        if regions:
            locations = get_locations(regions[0].id)
            if locations:
                starting_location_id = locations[0].id

        player = create_player(
            world_id=world_id,
            username=username,
            character_name=character_name,
            character_class=character_class,
            starting_location_id=starting_location_id,
        )

        # Record player joining event
        record_event(
            world_id=world_id,
            event_type="player_action",
            title=f"{character_name} Arrives",
            description=(
                f"A new adventurer named {character_name} "
                f"({character_class}) has arrived in the world."
            ),
            world_day=get_current_world_time(world_id).get(
                "total_days", 0.0
            ),
            player_id=player.id,
            location_id=starting_location_id,
            is_notable=True,
            importance=3,
        )

        return get_player_context(player.id, world_id)
    except Exception as e:
        logger.error(f"Player creation failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.get("/player/{player_id}/context", tags=["Stage 1 - World State"])
def get_player_context_endpoint(player_id: int, world_id: int):
    """Get complete player context."""
    context = get_player_context(player_id, world_id)
    if not context:
        raise HTTPException(404, f"Player {player_id} not found")
    return context


@app.get("/world/{world_id}/quests", tags=["Stage 1 - World State"])
def get_world_quests(world_id: int, location_id: int = None):
    """Get available quests."""
    quests = get_available_quests(world_id, location_id)
    return [
        {
            "id": q.id,
            "title": q.title,
            "description": q.description,
            "type": q.quest_type,
            "objectives": json.loads(q.objectives or "[]"),
            "rewards": json.loads(q.rewards or "{}"),
        }
        for q in quests
    ]


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "healthy",
        "service": "AI Game Master Engine",
        "version": "0.1.0",
    }