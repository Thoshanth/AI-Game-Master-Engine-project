import json
from backend.llm_client import chat_completion
from backend.world_engine.world_api import (
    get_location_context, get_player_context,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.procedural.world_context import build_world_context_string
from backend.database.world_store import (
    get_recent_events, get_available_quests,
)
from backend.multiplayer.connection_manager import manager
from backend.logger import get_logger

logger = get_logger("gm_agents.narrator")

# Atmosphere by time of day and season
ATMOSPHERE_TEMPLATES = {
    ("morning", "spring"): (
        "Golden light filters through budding branches. "
        "The air smells of fresh earth and possibility."
    ),
    ("morning", "summer"): (
        "The sun rises hot and bright. "
        "Already the heat shimmers off stone surfaces."
    ),
    ("morning", "autumn"): (
        "A crisp chill hangs in the amber morning air. "
        "Leaves spiral down on a gentle breeze."
    ),
    ("morning", "winter"): (
        "Frost glitters on every surface. "
        "Your breath steams in the freezing morning air."
    ),
    ("afternoon", "spring"): (
        "Warm afternoon sun illuminates the scene. "
        "Birds call in the distance."
    ),
    ("afternoon", "summer"): (
        "The afternoon heat is oppressive. "
        "Everything moves slowly, seeking shade."
    ),
    ("afternoon", "autumn"): (
        "The low autumn sun casts long golden shadows. "
        "The world feels melancholy and beautiful."
    ),
    ("afternoon", "winter"): (
        "The pale winter sun offers little warmth. "
        "Everything feels cold and exposed."
    ),
    ("evening", "spring"): (
        "The evening brings cool relief and firefly glimmers. "
        "Lanterns begin to flicker to life."
    ),
    ("evening", "summer"): (
        "The heat finally begins to lift. "
        "A welcome breeze stirs as night approaches."
    ),
    ("evening", "autumn"): (
        "Torches and lanterns cast pools of amber warmth "
        "against the gathering dark."
    ),
    ("evening", "winter"): (
        "Night falls fast and brutal. "
        "Every light source becomes precious."
    ),
    ("night", "spring"): (
        "The night is alive with spring sounds — "
        "frogs, crickets, distant owls."
    ),
    ("night", "summer"): (
        "A warm summer night, heavy with scents. "
        "The darkness feels close and intimate."
    ),
    ("night", "autumn"): (
        "The autumn night is clear and cold. "
        "Stars blaze with unusual intensity."
    ),
    ("night", "winter"): (
        "A bitter winter night. "
        "The cold is a physical presence, pressing in."
    ),
}


def narrator_agent(state: dict) -> dict:
    """
    Agent 1 — World Narrator

    Reads world state and generates vivid scene description.
    Called for: player_entered_location, scene_refresh,
                new_world_event, time_of_day_change.

    Reads:  world_id, player_id, trigger_data
    Writes: scene_description, atmosphere, sensory_details
    """
    world_id = state["world_id"]
    player_id = state["player_id"]
    trigger = state["trigger"]
    trigger_data = state.get("trigger_data", {})
    iteration = state.get("iterations", 0)

    logger.info(
        f"Narrator Agent | world={world_id} | "
        f"trigger={trigger} | iter={iteration}"
    )

    # Get location context
    location_id = trigger_data.get("location_id")
    location_context = {}
    if location_id:
        location_context = get_location_context(
            location_id, world_id
        )

    # Get world time and atmosphere
    world_time = get_current_world_time(world_id)
    time_of_day = world_time.get("time_of_day", "afternoon")
    season = world_time.get("season", "spring")

    atmosphere_key = (time_of_day, season)
    base_atmosphere = ATMOSPHERE_TEMPLATES.get(
        atmosphere_key,
        "The world feels alive with subtle tensions."
    )

    # Get online players at this location
    players_here = []
    if location_id:
        players_here = manager.get_players_at_location(
            world_id, location_id
        )

    # Get recent events at this location
    recent_events = get_recent_events(
        world_id, limit=3, location_id=location_id,
        notable_only=False,
    ) if location_id else []

    # Build location description
    location_info = location_context.get("location", {})
    npcs_present = location_context.get("npcs_present", [])
    rumors = location_info.get("rumors", [])
    current_events = location_info.get("current_events", [])

    npcs_str = "\n".join([
        f"- {npc['name']} ({npc['role']}) — "
        f"{npc['emotion']} — {npc['current_activity']}"
        for npc in npcs_present[:5]
    ]) or "No NPCs visible"

    players_str = ""
    if len(players_here) > 1:
        other_players = [
            p for p in players_here
            if p["player_id"] != player_id
        ]
        if other_players:
            players_str = (
                f"\nOther players present: "
                f"{', '.join(p['character_name'] for p in other_players)}"
            )

    events_str = "\n".join([
        f"- {e.title}: {e.description[:60]}"
        for e in recent_events
    ]) or "Nothing unusual recently"

    world_context = build_world_context_string(world_id)

    system_prompt = """You are the narrator for a dark fantasy RPG.
Write vivid, atmospheric scene descriptions that make players 
feel fully present in the world. Use sensory details.
Match the world's tone — dark, complex, morally ambiguous."""

    user_prompt = f"""{world_context}

Write a scene description for a player entering/observing this location.

Location: {location_info.get('name', 'Unknown')} ({location_info.get('type', 'unknown')})
Description: {location_info.get('description', '')}
Population: {location_info.get('population', 0)}
Safety: {location_info.get('safety_level', 5)}/10
Wealth: {location_info.get('wealth_level', 5)}/10

Time & Atmosphere:
{world_time.get('time_string', 'Unknown time')}
{base_atmosphere}

NPCs Present:
{npcs_str}
{players_str}

Current Events Here:
{events_str}

Active Rumors:
{chr(10).join(f'- {r.get("text", "") if isinstance(r, dict) else r}' for r in rumors[:2]) or 'None'}

Trigger: {trigger}

Write 3-4 sentences of immersive scene description:
- Start with the most striking visual element
- Include sounds and smells
- Reference the mood/atmosphere
- Mention what the player can interact with
- If other players are present, note them naturally

Then on a new line, list 3-5 things the player can do here:
ACTIONS:
- [action]: [brief description]"""

    try:
        response = chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.8,
        )

        # Split narration from actions
        parts = response.split("ACTIONS:")
        scene_text = parts[0].strip()
        actions_text = parts[1].strip() if len(parts) > 1 else ""

        # Parse suggested actions
        suggested_actions = []
        for line in actions_text.split("\n"):
            line = line.strip()
            if line.startswith("-"):
                suggested_actions.append(line[1:].strip())

        logger.info(
            f"Narrator complete | "
            f"chars={len(scene_text)} | "
            f"actions={len(suggested_actions)}"
        )

        return {
            "scene_description": scene_text,
            "atmosphere": base_atmosphere,
            "sensory_details": [
                scene_text[:100],
                base_atmosphere,
            ],
            "suggested_actions": suggested_actions,
            "agent_log": state.get("agent_log", []) + [{
                "agent": "Narrator",
                "iteration": iteration,
                "trigger": trigger,
                "location": location_info.get("name", "Unknown"),
                "chars_generated": len(scene_text),
            }],
        }

    except Exception as e:
        logger.error(f"Narrator agent failed: {e}", exc_info=True)
        fallback = (
            f"You find yourself in "
            f"{location_info.get('name', 'an unknown place')}. "
            f"{base_atmosphere} "
            f"Several figures move about their business."
        )
        return {
            "scene_description": fallback,
            "atmosphere": base_atmosphere,
            "sensory_details": [],
            "suggested_actions": [
                "Look around",
                "Talk to someone",
                "Move to another location",
            ],
            "agent_log": state.get("agent_log", []) + [{
                "agent": "Narrator",
                "error": str(e),
            }],
        }