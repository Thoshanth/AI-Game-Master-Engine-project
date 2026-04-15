import json
import random
from backend.llm_client import chat_completion_json
from backend.database.world_store import (
    record_event, get_world_summary, get_factions,
    get_recent_events, update_global_state,
    add_rumor_to_location, get_locations, get_regions,
)
from backend.procedural.world_context import build_world_context_string
from backend.world_engine.world_clock import get_current_world_time
from backend.npc_memory.memory_store import store_memory
from backend.database.db import SessionLocal, NPC, Location
from backend.logger import get_logger

logger = get_logger("narrative.consequence")

# Consequence templates by action type
# Defines what kinds of effects each action can have
CONSEQUENCE_TEMPLATES = {
    "player_killed_npc": {
        "severity": "major",
        "immediate": [
            "NPC is dead — location loses that entity",
            "Witnesses may report to authorities",
        ],
        "short_term": [
            "Family members enter mourning state",
            "Faction investigates if NPC was affiliated",
            "Economic impact if NPC was a merchant",
        ],
        "long_term": [
            "Bounty placed on player by faction",
            "New NPC fills the role — with different personality",
            "Player reputation drops across faction",
        ],
    },
    "player_helped_faction": {
        "severity": "moderate",
        "immediate": [
            "Faction reputation increases",
            "Faction leader aware of player",
        ],
        "short_term": [
            "Faction offers new quests to player",
            "Rival factions become suspicious of player",
        ],
        "long_term": [
            "Faction may grant player a title or reward",
            "Rival faction may target player",
        ],
    },
    "player_betrayed_faction": {
        "severity": "major",
        "immediate": [
            "Faction reputation drops severely",
            "Faction members become hostile",
        ],
        "short_term": [
            "Bounty placed on player within faction territory",
            "Rival factions learn of betrayal",
        ],
        "long_term": [
            "Faction sends assassin after player",
            "Other factions distrust player as untrustworthy",
        ],
    },
    "player_discovered_secret": {
        "severity": "moderate",
        "immediate": [
            "Player gains dangerous knowledge",
            "Secret holder becomes aware someone knows",
        ],
        "short_term": [
            "Secret holder tries to silence player",
            "Other interested parties learn player knows",
        ],
        "long_term": [
            "New quest chain opens around the secret",
            "Political balance may shift if secret is revealed",
        ],
    },
    "player_completed_major_quest": {
        "severity": "moderate",
        "immediate": [
            "Quest giver fulfilled — relationship improves",
            "World state changes per quest resolution",
        ],
        "short_term": [
            "Word spreads of player's achievement",
            "New opportunities open based on resolution",
        ],
        "long_term": [
            "Player reputation improves across region",
            "New story arcs unlock based on what they chose",
        ],
    },
    "player_started_war": {
        "severity": "catastrophic",
        "immediate": [
            "Faction mobilizes military forces",
            "Border regions become dangerous",
        ],
        "short_term": [
            "Trade routes disrupted — prices rise",
            "Refugees flee conflict zones",
            "NPCs take sides in the conflict",
        ],
        "long_term": [
            "Territory changes hands",
            "New political landscape emerges",
            "War-specific quests spawn",
        ],
    },
}


def generate_consequences(
    world_id: int,
    action_type: str,
    player_id: int,
    target_npc_id: int = None,
    target_faction_id: int = None,
    location_id: int = None,
    action_description: str = "",
) -> dict:
    """
    Generates specific consequences for a player action
    using the world context to make them relevant and unique.

    This is the function that makes the world feel responsive.
    Every major player action flows through here.
    """
    logger.info(
        f"Generating consequences | action={action_type} | "
        f"player={player_id} | world={world_id}"
    )

    world_context = build_world_context_string(world_id)
    world_time = get_current_world_time(world_id)
    template = CONSEQUENCE_TEMPLATES.get(
        action_type,
        CONSEQUENCE_TEMPLATES["player_discovered_secret"]
    )

    prompt = f"""{world_context}

A player just performed an action with major consequences.

Action Type: {action_type}
Action Description: {action_description}
Player ID: {player_id}
Location: {location_id or 'Unknown'}
Current World Day: {world_time.get('total_days', 0):.1f}

Generate specific, world-connected consequences for this action.
Make them feel like natural results of THIS specific world's politics,
factions, and recent events — not generic fantasy consequences.

Return ONLY valid JSON:
{{
    "action_summary": "1 sentence summarizing what happened",
    "severity": "minor|moderate|major|catastrophic",
    "immediate_consequences": [
        {{
            "description": "What happens right now",
            "affects": "npc|faction|location|world",
            "type": "reputation|economic|political|physical|social"
        }}
    ],
    "short_term_consequences": [
        {{
            "description": "What happens within 3 world days",
            "trigger_day": 1-3,
            "affects": "npc|faction|location|world"
        }}
    ],
    "long_term_consequences": [
        {{
            "description": "What happens within 2 weeks",
            "trigger_day": 7-14,
            "affects": "npc|faction|location|world"
        }}
    ],
    "rumors_generated": [
        "What people are saying about this"
    ],
    "quest_opportunities": [
        {{
            "title": "Quest title",
            "description": "Quest that emerges from this consequence",
            "quest_type": "revenge|investigation|protection|political"
        }}
    ],
    "world_state_impact": {{
        "economic": "none|minor|moderate|severe",
        "political": "none|minor|moderate|severe",
        "social": "none|minor|moderate|severe"
    }},
    "narrative_arc_potential": "Does this start a story arc? If so describe it briefly."
}}

Return valid JSON only."""

    try:
        raw = chat_completion_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a narrative consequence engine for an RPG. "
                        "Return valid JSON only."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
        )

        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        consequences = json.loads(cleaned.strip())

        # Record the action as a major world event
        record_event(
            world_id=world_id,
            event_type="player_action",
            title=consequences.get(
                "action_summary", f"Player action: {action_type}"
            ),
            description=action_description or consequences.get(
                "action_summary", ""
            ),
            world_day=world_time.get("total_days", 0.0),
            location_id=location_id,
            player_id=player_id,
            npc_id=target_npc_id,
            faction_id=target_faction_id,
            consequences=consequences.get("immediate_consequences", []),
            is_notable=True,
            importance=_severity_to_importance(
                consequences.get("severity", "moderate")
            ),
        )

        # Spread rumors to nearby locations
        rumors = consequences.get("rumors_generated", [])
        if rumors and location_id:
            _spread_rumors(world_id, location_id, rumors)

        # Store memories in nearby NPCs
        if action_description and target_npc_id:
            _store_witness_memories(
                world_id=world_id,
                location_id=location_id,
                action_description=action_description,
                player_id=player_id,
                world_day=world_time.get("total_days", 0.0),
            )

        # Schedule future consequences
        future_events = _schedule_future_consequences(
            world_id=world_id,
            player_id=player_id,
            short_term=consequences.get("short_term_consequences", []),
            long_term=consequences.get("long_term_consequences", []),
            current_day=world_time.get("total_days", 0.0),
        )

        consequences["scheduled_events"] = len(future_events)
        consequences["world_day"] = world_time.get("total_days", 0.0)

        logger.info(
            f"Consequences generated | "
            f"severity={consequences.get('severity')} | "
            f"immediate={len(consequences.get('immediate_consequences', []))} | "
            f"future={len(future_events)}"
        )

        return consequences

    except Exception as e:
        logger.error(f"Consequence generation failed: {e}", exc_info=True)
        raise


def _severity_to_importance(severity: str) -> int:
    return {
        "minor": 2,
        "moderate": 5,
        "major": 7,
        "catastrophic": 10,
    }.get(severity, 5)


def _spread_rumors(
    world_id: int,
    origin_location_id: int,
    rumors: list[str],
):
    """Spreads rumors to locations near the origin."""
    db = SessionLocal()
    try:
        regions = get_regions(world_id)
        all_locations = []
        for region in regions:
            locs = get_locations(region.id)
            all_locations.extend(locs)

        # Spread to 3 random nearby locations
        spread_to = random.sample(
            all_locations,
            min(3, len(all_locations))
        )
        for location in spread_to:
            for rumor in rumors[:2]:
                add_rumor_to_location(location.id, rumor)

        logger.debug(
            f"Rumors spread | count={len(rumors)} | "
            f"locations={len(spread_to)}"
        )
    finally:
        db.close()


def _store_witness_memories(
    world_id: int,
    location_id: int,
    action_description: str,
    player_id: int,
    world_day: float,
):
    """
    NPCs present at the location witness the action
    and store it as a memory — they will talk about it.
    """
    if not location_id:
        return

    db = SessionLocal()
    try:
        npcs_present = db.query(NPC).filter(
            NPC.location_id == location_id,
            NPC.is_alive == True,
        ).all()

        for npc in npcs_present[:5]:
            memory_text = (
                f"I witnessed: {action_description}. "
                f"This happened at my location."
            )
            store_memory(
                npc_id=npc.id,
                memory_text=memory_text,
                player_id=player_id,
                event_type="witnessed_event",
                emotion_at_time="shocked",
                relationship_delta=-0.1,
                world_day=world_day,
                importance=6,
            )

        logger.debug(
            f"Witness memories stored | "
            f"npcs={len(npcs_present[:5])}"
        )
    finally:
        db.close()


def _schedule_future_consequences(
    world_id: int,
    player_id: int,
    short_term: list,
    long_term: list,
    current_day: float,
) -> list:
    """
    Stores future consequences in the database
    so the world tick can execute them at the right time.
    """
    scheduled = []

    for consequence in short_term:
        trigger_day = current_day + consequence.get("trigger_day", 2)
        event = record_event(
            world_id=world_id,
            event_type="world_event",
            title="Scheduled consequence",
            description=consequence.get("description", ""),
            world_day=trigger_day,
            player_id=player_id,
            is_notable=False,
            importance=3,
        )
        scheduled.append(event)

    for consequence in long_term:
        trigger_day = current_day + consequence.get("trigger_day", 10)
        event = record_event(
            world_id=world_id,
            event_type="world_event",
            title="Long-term consequence",
            description=consequence.get("description", ""),
            world_day=trigger_day,
            player_id=player_id,
            is_notable=False,
            importance=5,
        )
        scheduled.append(event)

    return scheduled