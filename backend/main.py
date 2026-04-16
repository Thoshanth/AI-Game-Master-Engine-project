import json
import time
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from backend.narrative.narrative_pipeline import (
    process_player_action,
    run_narrative_tick,
)
from backend.narrative.arc_generator import (
    generate_story_arc,
    get_active_arcs,
    get_all_arcs,
    advance_arc_stage,
    resolve_arc,
    load_arc,
)
from backend.narrative.plot_tracker import (
    get_world_narrative_state,
    get_all_threads,
)
from backend.narrative.player_profiler import analyze_player_behavior
from backend.narrative.consequence_engine import generate_consequences
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
from backend.procedural.location_generator import (
    create_procedural_location,
    generate_complete_dungeon,
)
from backend.procedural.npc_generator import create_procedural_npc
from backend.procedural.item_generator import (
    generate_item_with_lore,
    generate_treasure_hoard,
)
from backend.procedural.event_generator import (
    generate_world_event,
    run_autonomous_world_tick,
)
from backend.npc_memory.dialogue_engine import generate_npc_dialogue
from backend.npc_memory.memory_store import (
    store_memory,
    get_all_memories_with_player,
    get_memory_count,
)
from backend.npc_memory.relationship_engine import (
    get_npc_relationship_with_player,
)
from backend.npc_memory.emotion_engine import (
    decay_emotions,
    update_npc_emotion,
)
from backend.prediction.sequence_predictor import predict_next_actions
from backend.prediction.engagement_scorer import (
    calculate_session_engagement,
)
from backend.prediction.frustration_detector import detect_frustration
from backend.prediction.skill_assessor import assess_player_skill
from backend.prediction.prediction_pipeline import (
    full_player_prediction,
    pre_generate_predicted_content,
)
from backend.npc_memory.personality_engine import get_personality_profile
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

# ══════════════════════════════════════════════════════════════════
# STAGE 2 — Procedural World Generator
# ══════════════════════════════════════════════════════════════════

@app.post("/generate/location", tags=["Stage 2 - Procedural"])
def generate_location(
    world_id: int,
    region_id: int,
    location_type: str = None,
    name: str = None,
):
    """
    Procedurally generates a new location.
    Type and content are determined by terrain biome.
    All content is consistent with current world state.

    location_type: city|village|dungeon|tavern|castle|ruins|mine|temple
    Leave empty to auto-select based on terrain.
    """
    logger.info(f"Generate location | world={world_id} | region={region_id}")
    try:
        result = create_procedural_location(
            world_id=world_id,
            region_id=region_id,
            location_type=location_type,
            name=name,
        )
        return result
    except Exception as e:
        logger.error(f"Location generation failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.post("/generate/dungeon", tags=["Stage 2 - Procedural"])
def generate_dungeon(
    world_id: int,
    region_id: int,
    danger_level: int = None,
    theme: str = None,
):
    """
    Generates a complete dungeon with:
    - 3 floors with enemies, hazards, treasures
    - Boss encounter with lore
    - Unique legendary treasure
    - Quest hooks connected to world events

    danger_level: 1-10 (default: matches region)
    theme: optional flavor (e.g. 'undead', 'dwarven', 'arcane')
    """
    logger.info(f"Generate dungeon | world={world_id} | region={region_id}")
    try:
        result = generate_complete_dungeon(
            world_id=world_id,
            region_id=region_id,
            danger_level=danger_level,
            theme=theme,
        )
        return result
    except Exception as e:
        logger.error(f"Dungeon generation failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.post("/generate/npc", tags=["Stage 2 - Procedural"])
def generate_npc_endpoint(
    world_id: int,
    location_id: int,
    role: str = "peasant",
    faction_id: int = None,
):
    """
    Generates a context-aware NPC.

    The NPC knows world events, has opinions about factions,
    and has personal goals connected to the current world state.

    role: merchant|guard|innkeeper|blacksmith|mage|priest|
          thief|noble|peasant|warrior|quest_giver|villain
    """
    logger.info(
        f"Generate NPC | world={world_id} | "
        f"location={location_id} | role={role}"
    )
    try:
        result = create_procedural_npc(
            world_id=world_id,
            location_id=location_id,
            role=role,
            faction_id=faction_id,
        )
        return result
    except Exception as e:
        logger.error(f"NPC generation failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.post("/generate/item", tags=["Stage 2 - Procedural"])
def generate_item_endpoint(
    world_id: int,
    item_type: str = None,
    rarity: str = None,
    location_context: str = None,
):
    """
    Generates an item with lore connected to world history.

    item_type: weapon|armor|potion|artifact|tool|key
    rarity: common|uncommon|rare|legendary
    location_context: optional description of where it was found
    """
    logger.info(f"Generate item | world={world_id} | type={item_type}")
    try:
        result = generate_item_with_lore(
            world_id=world_id,
            item_type=item_type,
            rarity=rarity,
            location_context=location_context,
        )
        return result
    except Exception as e:
        logger.error(f"Item generation failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.post("/generate/treasure", tags=["Stage 2 - Procedural"])
def generate_treasure_endpoint(
    world_id: int,
    danger_level: int = 5,
    location_context: str = None,
):
    """
    Generates a full treasure hoard.
    Number and quality of items scales with danger level.
    """
    logger.info(
        f"Generate treasure | world={world_id} | danger={danger_level}"
    )
    try:
        result = generate_treasure_hoard(
            world_id=world_id,
            danger_level=danger_level,
            location_context=location_context,
        )
        return {"items": result, "total_items": len(result)}
    except Exception as e:
        logger.error(f"Treasure generation failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.post("/generate/event", tags=["Stage 2 - Procedural"])
def generate_event_endpoint(
    world_id: int,
    event_category: str = None,
    region_id: int = None,
):
    """
    Generates a world event based on current world state.

    event_category: faction_conflict|economic|natural|political|mysterious
    Leave empty to auto-select based on world tensions.
    """
    logger.info(
        f"Generate event | world={world_id} | category={event_category}"
    )
    try:
        result = generate_world_event(
            world_id=world_id,
            event_category=event_category,
            region_id=region_id,
        )
        return result
    except Exception as e:
        logger.error(f"Event generation failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.post("/world/{world_id}/tick", tags=["Stage 2 - Procedural"])
def world_tick(world_id: int):
    """
    Runs one autonomous world tick.
    Generates events that happen without player involvement.

    In production this runs automatically every 15 minutes.
    Call manually to test autonomous world behavior.
    """
    logger.info(f"Manual world tick | world_id={world_id}")
    try:
        events = run_autonomous_world_tick(world_id)
        return {
            "events_generated": len(events),
            "events": events,
        }
    except Exception as e:
        logger.error(f"World tick failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.post("/generate/expand-world", tags=["Stage 2 - Procedural"])
def expand_world(
    world_id: int,
    num_locations: int = 3,
    num_npcs: int = 5,
):
    """
    Expands the world by generating multiple new locations and NPCs.
    Distributes content across all regions.
    """
    logger.info(f"Expanding world | world_id={world_id}")
    try:
        regions = get_regions(world_id)
        if not regions:
            raise HTTPException(404, "No regions found")

        created_locations = []
        created_npcs = []

        # Generate new locations
        for i in range(num_locations):
            region = random.choice(regions)
            try:
                location = create_procedural_location(
                    world_id=world_id,
                    region_id=region.id,
                )
                created_locations.append({
                    "id": location["id"],
                    "name": location["name"],
                    "type": location["type"],
                    "region": location["region"],
                })
            except Exception as e:
                logger.warning(f"Location {i+1} failed: {e}")

        # Generate new NPCs in existing locations
        from backend.database.world_store import get_locations
        npc_roles = [
            "merchant", "guard", "mage", "priest",
            "thief", "warrior", "peasant", "innkeeper",
        ]

        for i in range(num_npcs):
            region = random.choice(regions)
            locations = get_locations(region.id)
            if not locations:
                continue
            location = random.choice(locations)
            role = random.choice(npc_roles)
            try:
                npc = create_procedural_npc(
                    world_id=world_id,
                    location_id=location.id,
                    role=role,
                )
                created_npcs.append({
                    "id": npc["id"],
                    "name": npc["name"],
                    "role": npc["role"],
                    "location": npc["location"],
                })
            except Exception as e:
                logger.warning(f"NPC {i+1} failed: {e}")

        return {
            "locations_created": len(created_locations),
            "npcs_created": len(created_npcs),
            "locations": created_locations,
            "npcs": created_npcs,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"World expansion failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))
    
# ══════════════════════════════════════════════════════════════════
# STAGE 3 — NPC Memory & Personality System
# ══════════════════════════════════════════════════════════════════

@app.post("/npc/{npc_id}/interact", tags=["Stage 3 - NPC Memory"])
def interact_with_npc(
    npc_id: int,
    player_id: int,
    player_message: str,
    action_type: str = "player_questioned",
    world_id: int = None,
):
    """
    Player interacts with an NPC.

    The NPC responds using:
    - Their personality (Big Five traits)
    - Retrieved memories of this player
    - Current emotion state
    - Relationship score with the player
    - Current world events

    action_type determines relationship impact:
    player_helped | player_gave_gift | player_complimented |
    player_attacked | player_stole | player_lied |
    player_threatened | player_traded | player_questioned |
    player_betrayed | player_defended
    """
    logger.info(
        f"NPC interact | npc={npc_id} | "
        f"player={player_id} | action={action_type}"
    )
    try:
        result = generate_npc_dialogue(
            npc_id=npc_id,
            player_id=player_id,
            player_message=player_message,
            action_type=action_type,
            world_id=world_id,
        )
        return result
    except Exception as e:
        logger.error(f"NPC interaction failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.get("/npc/{npc_id}/memory/{player_id}", tags=["Stage 3 - NPC Memory"])
def get_npc_memory(npc_id: int, player_id: int):
    """
    Get all memories an NPC has of a specific player.
    Shows the full interaction history from the NPC's perspective.
    """
    memories = get_all_memories_with_player(npc_id, player_id)
    count = get_memory_count(npc_id)
    return {
        "npc_id": npc_id,
        "player_id": player_id,
        "total_npc_memories": count,
        "memories_with_player": len(memories),
        "memories": memories,
    }


@app.get("/npc/{npc_id}/relationship/{player_id}", tags=["Stage 3 - NPC Memory"])
def get_relationship(npc_id: int, player_id: int):
    """
    Get the relationship status between an NPC and player.
    Returns score, label, interaction history summary.
    """
    result = get_npc_relationship_with_player(npc_id, player_id)
    if not result:
        raise HTTPException(404, "NPC or player not found")
    return result


@app.get("/npc/{npc_id}/personality", tags=["Stage 3 - NPC Memory"])
def get_npc_personality(npc_id: int):
    """
    Get an NPC's full personality profile.
    Shows Big Five traits, dialogue style, behavioral tendencies.
    """
    result = get_personality_profile(npc_id)
    if not result:
        raise HTTPException(404, f"NPC {npc_id} not found")
    return result


@app.post("/npc/{npc_id}/remember", tags=["Stage 3 - NPC Memory"])
def add_npc_memory(
    npc_id: int,
    memory_text: str,
    player_id: int = None,
    event_type: str = "world_event",
    importance: int = 5,
    world_day: float = 0.0,
):
    """
    Manually adds a memory to an NPC.
    Used by the world simulation when significant events happen
    that the NPC should know about even without direct player interaction.

    importance: 1-10 (10 = life-changing, 1 = minor detail)
    """
    memory_id = store_memory(
        npc_id=npc_id,
        memory_text=memory_text,
        player_id=player_id,
        event_type=event_type,
        importance=importance,
        world_day=world_day,
    )
    return {
        "memory_id": memory_id,
        "npc_id": npc_id,
        "memory_text": memory_text,
        "stored": True,
    }


@app.post("/world/{world_id}/decay-emotions", tags=["Stage 3 - NPC Memory"])
def decay_world_emotions(world_id: int, days_passed: float = 1.0):
    """
    Applies emotion decay to all NPCs in the world.
    Strong emotions fade over time — NPCs forgive (slowly).

    Called automatically by the world tick.
    Call manually to simulate time passing.
    """
    decay_emotions(world_id, days_passed)
    return {
        "world_id": world_id,
        "days_passed": days_passed,
        "status": "emotions decayed",
    }
# ══════════════════════════════════════════════════════════════════
# STAGE 4 — Dynamic Narrative Engine
# ══════════════════════════════════════════════════════════════════

@app.post("/narrative/consequence", tags=["Stage 4 - Narrative"])
def trigger_consequence(
    world_id: int,
    player_id: int,
    action_type: str,
    action_description: str,
    location_id: int = None,
    target_npc_id: int = None,
    target_faction_id: int = None,
    generate_arc: bool = False,
):
    """
    Triggers the full narrative pipeline for a player action.

    Generates consequences, updates player profile,
    optionally creates story arc, records plot thread.

    action_type options:
    player_killed_npc | player_helped_faction |
    player_betrayed_faction | player_discovered_secret |
    player_completed_major_quest | player_started_war

    generate_arc: set True to force a new story arc from this action
    """
    logger.info(
        f"Narrative consequence | action={action_type} | "
        f"player={player_id}"
    )
    try:
        result = process_player_action(
            world_id=world_id,
            player_id=player_id,
            action_type=action_type,
            action_description=action_description,
            location_id=location_id,
            target_npc_id=target_npc_id,
            target_faction_id=target_faction_id,
            generate_arc=generate_arc,
        )
        return result
    except Exception as e:
        logger.error(f"Consequence failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.get("/narrative/arcs/{world_id}", tags=["Stage 4 - Narrative"])
def get_story_arcs(world_id: int, active_only: bool = True):
    """
    Get all story arcs in the world.
    Each arc has a stage: setup → rising → climax → resolved.
    """
    try:
        if active_only:
            arcs = get_active_arcs(world_id)
        else:
            arcs = get_all_arcs(world_id)

        return {
            "world_id": world_id,
            "total_arcs": len(arcs),
            "arcs": [
                {
                    "arc_id": a.get("arc_id"),
                    "title": a.get("title"),
                    "type": a.get("type"),
                    "logline": a.get("logline"),
                    "stage": a.get("stage"),
                    "status": a.get("status"),
                    "urgency": a.get("urgency"),
                    "created_day": a.get("created_day"),
                }
                for a in arcs
            ],
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/narrative/arc/generate", tags=["Stage 4 - Narrative"])
def create_story_arc(
    world_id: int,
    arc_type: str = None,
    trigger_event: str = None,
    player_id: int = None,
):
    """
    Generates a new story arc from current world state.

    arc_type: political_intrigue|mystery|faction_war|
              personal_revenge|ancient_threat|
              economic_crisis|romance_tragedy

    The arc includes setup, rising action, climax,
    and 3 possible resolutions based on player choices.
    """
    logger.info(
        f"Generate arc | world={world_id} | type={arc_type}"
    )
    try:
        arc = generate_story_arc(
            world_id=world_id,
            trigger_event=trigger_event,
            player_id=player_id,
            arc_type=arc_type,
        )
        return arc
    except Exception as e:
        logger.error(f"Arc generation failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.get("/narrative/arc/{arc_id}", tags=["Stage 4 - Narrative"])
def get_story_arc(arc_id: str):
    """Get full details of a specific story arc."""
    arc = load_arc(arc_id)
    if not arc:
        raise HTTPException(404, f"Arc {arc_id} not found")
    return arc


@app.post("/narrative/arc/{arc_id}/advance", tags=["Stage 4 - Narrative"])
def advance_story_arc(arc_id: str, new_stage: str):
    """
    Manually advance a story arc to its next stage.
    Stages: setup → rising → climax → resolved

    The narrative tick does this automatically over time.
    """
    result = advance_arc_stage(arc_id, new_stage)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.post("/narrative/arc/{arc_id}/resolve", tags=["Stage 4 - Narrative"])
def resolve_story_arc(arc_id: str, resolution_id: str):
    """
    Resolves a story arc with a specific ending.
    resolution_id: resolution_a | resolution_b | resolution_c

    Each resolution produces different world consequences.
    """
    result = resolve_arc(arc_id, resolution_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.get("/narrative/player/{player_id}/profile", tags=["Stage 4 - Narrative"])
def get_player_profile(player_id: int):
    """
    Analyze player behavior and return Bartle type profile.

    Types: explorer | achiever | socializer | killer

    Used by the narrative engine to customize world content
    to match this player's preferred play style.
    """
    try:
        profile = analyze_player_behavior(player_id)
        if not profile:
            raise HTTPException(404, f"Player {player_id} not found")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/narrative/threads/{world_id}", tags=["Stage 4 - Narrative"])
def get_plot_threads(world_id: int):
    """
    Get all active plot threads in the world.
    Threads are the individual storylines being tracked.
    Arcs contain multiple threads.
    """
    try:
        threads = get_all_threads(world_id)
        return {
            "world_id": world_id,
            "total_threads": len(threads),
            "active": sum(
                1 for t in threads if t.get("status") == "active"
            ),
            "resolved": sum(
                1 for t in threads if t.get("status") == "resolved"
            ),
            "threads": threads,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/narrative/state/{world_id}", tags=["Stage 4 - Narrative"])
def get_narrative_state(world_id: int):
    """
    Complete narrative state of the world.
    Shows all arcs, threads, connections, and tensions.
    The Game Master's full picture of the story.
    """
    try:
        return get_world_narrative_state(world_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/narrative/tick/{world_id}", tags=["Stage 4 - Narrative"])
def narrative_tick(world_id: int):
    """
    Advances the narrative state of the world.

    Automatically:
    - Advances story arc stages based on time elapsed
    - Decays NPC emotions
    - Runs autonomous world events
    - Auto-resolves expired arcs

    In production this runs every 15 minutes via scheduler.
    Call manually to test narrative progression.
    """
    try:
        result = run_narrative_tick(world_id)
        return result
    except Exception as e:
        logger.error(f"Narrative tick failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))
    
# ══════════════════════════════════════════════════════════════════
# STAGE 5 — Player Behavior Predictor
# ══════════════════════════════════════════════════════════════════

@app.get("/predict/next-action/{player_id}", tags=["Stage 5 - Prediction"])
def get_next_action_prediction(
    player_id: int,
    n_predictions: int = 3,
):
    """
    Predicts the player's next most likely actions
    using a personalized Markov transition matrix.

    Each prediction includes:
    - Predicted action type
    - Confidence score
    - Content that should be pre-generated
    - Alignment with player's Bartle type

    More accurate as player accumulates more action history.
    """
    logger.info(f"Next action prediction | player={player_id}")
    try:
        return predict_next_actions(player_id, n_predictions)
    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.get("/predict/engagement/{player_id}", tags=["Stage 5 - Prediction"])
def get_engagement_score(
    player_id: int,
    session_hours: float = 24.0,
):
    """
    Calculates engagement score for the player's recent session.

    Score 0-10:
    8-10 = Highly engaged
    6-8  = Engaged
    4-6  = Moderate
    2-4  = Low engagement
    0-2  = Disengaged

    Returns most engaging content type and recommendations.
    """
    logger.info(f"Engagement scoring | player={player_id}")
    try:
        return calculate_session_engagement(player_id, session_hours)
    except Exception as e:
        logger.error(f"Engagement scoring failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.get("/predict/frustration/{player_id}", tags=["Stage 5 - Prediction"])
def get_frustration_level(
    player_id: int,
    window_minutes: int = 30,
):
    """
    Detects frustration signals in recent player behavior.

    Signals detected:
    - Repeated actions (stuck/confused)
    - Action frequency drop (bored/lost)
    - Aggressive escalation (frustrated)
    - Quest abandonment (unclear objectives)
    - Aimless wandering (lost/directionless)

    Returns frustration level + specific intervention suggestions.
    """
    logger.info(f"Frustration detection | player={player_id}")
    try:
        return detect_frustration(player_id, window_minutes)
    except Exception as e:
        logger.error(f"Frustration detection failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.get("/predict/skill/{player_id}", tags=["Stage 5 - Prediction"])
def get_skill_assessment(player_id: int):
    """
    Assesses player skill level across 5 dimensions:
    - Quest completion rate
    - Combat effectiveness
    - Discovery rate
    - Action diversity
    - Decision speed

    Returns overall skill level and difficulty recommendations
    for content generation.

    Levels: novice → beginner → intermediate → advanced → expert
    """
    logger.info(f"Skill assessment | player={player_id}")
    try:
        return assess_player_skill(player_id)
    except Exception as e:
        logger.error(f"Skill assessment failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.post("/predict/full/{player_id}", tags=["Stage 5 - Prediction"])
def get_full_prediction(player_id: int, world_id: int):
    """
    Complete behavioral analysis combining all 5 systems:

    1. Next action prediction (Markov chain)
    2. Engagement scoring (0-10 score + recommendations)
    3. Frustration detection (signals + interventions)
    4. Skill assessment (novice → expert)
    5. Bartle type profile (explorer/achiever/socializer/killer)

    Returns unified recommendations and pre-generation needs.
    Used by the Game Master Agent (Stage 9) to adapt the world.
    """
    logger.info(f"Full prediction | player={player_id}")
    try:
        return full_player_prediction(player_id, world_id)
    except Exception as e:
        logger.error(f"Full prediction failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@app.post("/predict/pre-generate/{player_id}", tags=["Stage 5 - Prediction"])
def pre_generate_for_player(player_id: int, world_id: int):
    """
    Pre-generates content based on behavioral predictions.

    If player is predicted to move → pre-generates a location.
    If player is predicted to seek NPC → pre-generates an NPC.

    This ensures zero wait time for players —
    content is ready before they ask for it.
    """
    logger.info(f"Pre-generation | player={player_id}")
    try:
        return pre_generate_predicted_content(player_id, world_id)
    except Exception as e:
        logger.error(f"Pre-generation failed: {e}", exc_info=True)
        raise HTTPException(500, str(e))