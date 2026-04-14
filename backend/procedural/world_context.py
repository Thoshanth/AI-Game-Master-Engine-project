import json
from backend.database.world_store import (
    get_world_summary, get_factions, get_recent_events,
    get_regions, get_world,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.logger import get_logger

logger = get_logger("procedural.context")


def build_world_context_string(world_id: int) -> str:
    """
    Builds a comprehensive world context string.
    Injected into every LLM prompt to ensure consistency.

    This is the key to coherent procedural generation —
    the LLM knows the full world state before generating anything.
    """
    logger.debug(f"Building world context | world_id={world_id}")

    world = get_world(world_id)
    if not world:
        return "Unknown world."

    summary = get_world_summary(world_id)
    world_time = get_current_world_time(world_id)
    factions = get_factions(world_id)
    recent_events = get_recent_events(
        world_id, limit=5, notable_only=True
    )
    global_state = json.loads(world.global_state or "{}")

    # Build faction summary
    faction_summary = []
    for f in factions:
        goals = json.loads(f.current_goals or "[]")
        faction_summary.append(
            f"- {f.name} ({f.faction_type}): "
            f"{f.description[:80]} "
            f"Goals: {', '.join(goals[:2]) if goals else 'unknown'}"
        )

    # Build recent events summary
    events_summary = []
    for e in recent_events:
        events_summary.append(f"- {e.title}: {e.description[:80]}")

    context = f"""=== WORLD STATE CONTEXT ===
World: {world.name}
Description: {world.description}

Current Time: {world_time.get('time_string', 'Unknown')}
Season: {world_time.get('season', 'spring').title()}

World Statistics:
- Regions: {summary.get('statistics', {}).get('regions', 0)}
- Living NPCs: {summary.get('statistics', {}).get('living_npcs', 0)}
- Active Players: {summary.get('statistics', {}).get('players', 0)}
- Active Factions: {summary.get('statistics', {}).get('active_factions', 0)}

Active Factions:
{chr(10).join(faction_summary) or 'No major factions known'}

Current World State:
- Economic State: {global_state.get('economic_state', 'stable')}
- Active Wars: {', '.join(global_state.get('active_wars', [])) or 'None'}
- Political Tensions: {', '.join(global_state.get('political_tensions', [])) or 'None'}

Recent Notable Events:
{chr(10).join(events_summary) or 'No recent notable events'}
=== END WORLD CONTEXT ==="""

    logger.debug(f"World context built | chars={len(context)}")
    return context


def build_location_context_string(
    region_name: str,
    terrain_type: str,
    danger_level: int,
    controlling_faction: str = None,
    nearby_locations: list = None,
) -> str:
    """Builds location-specific context for generation."""
    nearby = ", ".join(nearby_locations or []) or "None known"
    faction_info = (
        f"Controlled by: {controlling_faction}"
        if controlling_faction
        else "No clear controlling faction"
    )

    return f"""=== LOCATION CONTEXT ===
Region: {region_name}
Terrain: {terrain_type}
Danger Level: {danger_level}/10
{faction_info}
Nearby Locations: {nearby}
=== END LOCATION CONTEXT ==="""


def build_npc_generation_context(
    world_id: int,
    location_name: str,
    location_type: str,
    faction_name: str = None,
    player_reputation: dict = None,
) -> str:
    """Builds context for NPC generation."""
    world_context = build_world_context_string(world_id)

    player_rep_str = ""
    if player_reputation:
        rep_items = [
            f"{k}: {v}" for k, v in player_reputation.items()
        ]
        player_rep_str = (
            f"Known player reputations in this area: "
            f"{', '.join(rep_items)}"
        )

    return f"""{world_context}

=== NPC GENERATION CONTEXT ===
Location: {location_name} ({location_type})
Faction Affiliation: {faction_name or 'None'}
{player_rep_str}
=== END NPC CONTEXT ==="""