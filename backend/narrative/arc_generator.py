import json
import random
from pathlib import Path
from datetime import datetime
from backend.llm_client import chat_completion_json
from backend.procedural.world_context import build_world_context_string
from backend.database.world_store import (
    get_recent_events, get_factions, get_world_summary,
    record_event, create_quest, get_regions, get_locations,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.database.db import QuestState
from backend.logger import get_logger

logger = get_logger("narrative.arcs")

ARC_STORAGE_PATH = Path("game_data/story_arcs")
ARC_STORAGE_PATH.mkdir(parents=True, exist_ok=True)


def save_arc(world_id: int, arc: dict) -> str:
    """Saves a story arc to disk."""
    arc_id = arc.get("arc_id", f"arc_{world_id}_{datetime.utcnow().timestamp():.0f}")
    arc["arc_id"] = arc_id
    arc_path = ARC_STORAGE_PATH / f"{arc_id}.json"
    with open(arc_path, "w") as f:
        json.dump(arc, f, indent=2)
    logger.debug(f"Arc saved | arc_id={arc_id}")
    return arc_id


def load_arc(arc_id: str) -> dict:
    """Loads a story arc from disk."""
    arc_path = ARC_STORAGE_PATH / f"{arc_id}.json"
    if not arc_path.exists():
        return {}
    with open(arc_path) as f:
        return json.load(f)


def get_all_arcs(world_id: int) -> list[dict]:
    """Returns all story arcs for a world."""
    arcs = []
    for arc_file in ARC_STORAGE_PATH.glob(f"arc_{world_id}_*.json"):
        with open(arc_file) as f:
            arcs.append(json.load(f))
    return sorted(arcs, key=lambda a: a.get("created_day", 0))


def get_active_arcs(world_id: int) -> list[dict]:
    """Returns only active (not resolved) story arcs."""
    all_arcs = get_all_arcs(world_id)
    return [
        a for a in all_arcs
        if a.get("status") in ["active", "rising", "climax"]
    ]


def generate_story_arc(
    world_id: int,
    trigger_event: str = None,
    player_id: int = None,
    arc_type: str = None,
    faction_id: int = None,
) -> dict:
    """
    Generates a complete story arc with:
    - Setup: the initial situation
    - Rising action: escalating events
    - Climax: peak conflict
    - Multiple possible resolutions based on player choices

    The arc is connected to real world events, factions, and
    NPCs that exist in the world.
    """
    logger.info(
        f"Generating story arc | world={world_id} | "
        f"type={arc_type} | trigger='{trigger_event}'"
    )

    world_context = build_world_context_string(world_id)
    world_time = get_current_world_time(world_id)
    recent_events = get_recent_events(
        world_id, limit=5, notable_only=True
    )
    factions = get_factions(world_id)

    recent_events_str = "\n".join([
        f"- {e.title}: {e.description[:80]}"
        for e in recent_events
    ]) or "No recent notable events"

    factions_str = "\n".join([
        f"- {f.name} ({f.faction_type}): {f.description[:60]}"
        for f in factions
    ]) or "No major factions"

    arc_type_hint = arc_type or random.choice([
        "political_intrigue", "mystery", "faction_war",
        "personal_revenge", "ancient_threat",
        "economic_crisis", "romance_tragedy",
    ])

    prompt = f"""{world_context}

Generate a complete story arc for this RPG world.

Arc Type: {arc_type_hint}
{f'Triggered by: {trigger_event}' if trigger_event else ''}
{f'Connected to player: {player_id}' if player_id else ''}
Current World Day: {world_time.get("total_days", 0):.1f}

Recent Notable Events:
{recent_events_str}

Active Factions:
{factions_str}

Design a multi-stage story arc with real stakes and player agency.

Return ONLY valid JSON:
{{
    "title": "Arc title (dramatic, memorable)",
    "type": "{arc_type_hint}",
    "logline": "One sentence: what this story is about",
    "theme": "The thematic question this arc explores",
    "stage": "setup",
    "status": "active",
    "setup": {{
        "description": "3-4 sentences establishing the situation",
        "key_npcs": ["NPC roles involved"],
        "key_factions": ["Faction names involved"],
        "player_entry_point": "How does the player become involved?"
    }},
    "rising_action": {{
        "events": [
            {{
                "day_offset": 2,
                "event": "First escalation",
                "world_change": "How the world changes"
            }},
            {{
                "day_offset": 5,
                "event": "Second escalation",
                "world_change": "How the world changes"
            }},
            {{
                "day_offset": 10,
                "event": "Third escalation — things get worse",
                "world_change": "How the world changes"
            }}
        ]
    }},
    "climax": {{
        "description": "The peak conflict moment",
        "decision_point": "What choice must the player make?",
        "options": [
            {{
                "choice": "Option A description",
                "consequence": "What happens if they choose this"
            }},
            {{
                "choice": "Option B description",
                "consequence": "What happens if they choose this"
            }},
            {{
                "choice": "Option C - do nothing",
                "consequence": "What happens if player ignores it"
            }}
        ]
    }},
    "possible_resolutions": [
        {{
            "id": "resolution_a",
            "condition": "Player chose Option A",
            "description": "How the story ends",
            "world_impact": "Permanent world change",
            "player_reward": "What player gains"
        }},
        {{
            "id": "resolution_b",
            "condition": "Player chose Option B",
            "description": "How the story ends differently",
            "world_impact": "Different permanent world change",
            "player_reward": "Different reward"
        }},
        {{
            "id": "resolution_c",
            "condition": "Player ignored the arc",
            "description": "How the world resolves without player",
            "world_impact": "Usually negative outcome",
            "player_reward": "None — missed opportunity"
        }}
    ],
    "connected_quests": [
        {{
            "title": "Quest that is part of this arc",
            "description": "Quest description",
            "arc_stage": "setup|rising|climax"
        }}
    ],
    "urgency": "low|medium|high|critical",
    "estimated_duration_days": 5-30
}}

Return valid JSON only."""

    try:
        raw = chat_completion_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a narrative designer for an RPG. "
                        "Return valid JSON only."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=2500,
        )

        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        arc = json.loads(cleaned.strip())

        # Add metadata
        arc["world_id"] = world_id
        arc["player_id"] = player_id
        arc["created_day"] = world_time.get("total_days", 0.0)
        arc["trigger_event"] = trigger_event
        arc["resolution_chosen"] = None

        # Save arc
        arc_id = save_arc(world_id, arc)

        # Record as world event
        record_event(
            world_id=world_id,
            event_type="world_event",
            title=f"Story Arc Begins: {arc.get('title')}",
            description=arc.get("logline", ""),
            world_day=world_time.get("total_days", 0.0),
            player_id=player_id,
            is_notable=True,
            importance=7,
        )

        # Create the first quest from this arc
        quests = arc.get("connected_quests", [])
        if quests:
            first_quest = quests[0]
            regions = get_regions(world_id)
            location_id = None
            if regions:
                locs = get_locations(regions[0].id)
                if locs:
                    location_id = locs[0].id

            created_quest = create_quest(
                world_id=world_id,
                title=first_quest.get("title", "Unknown Quest"),
                description=first_quest.get("description", ""),
                quest_type="arc",
                origin_location_id=location_id,
                objectives=[
                    {
                        "id": 1,
                        "description": "Investigate the situation",
                        "completed": False,
                    }
                ],
                rewards={"experience": 500, "gold": 200},
                world_day=world_time.get("total_days", 0.0),
            )

            # Set quest to available
            from backend.database.db import SessionLocal, Quest
            db = SessionLocal()
            try:
                q = db.query(Quest).filter(
                    Quest.id == created_quest.id
                ).first()
                if q:
                    q.state = QuestState.AVAILABLE
                    db.commit()
            finally:
                db.close()

        logger.info(
            f"Story arc generated | "
            f"title='{arc.get('title')}' | "
            f"type={arc_type_hint} | "
            f"arc_id={arc_id}"
        )

        return arc

    except Exception as e:
        logger.error(f"Arc generation failed: {e}", exc_info=True)
        raise


def advance_arc_stage(arc_id: str, new_stage: str) -> dict:
    """Advances a story arc to its next stage."""
    arc = load_arc(arc_id)
    if not arc:
        return {"error": f"Arc {arc_id} not found"}

    valid_stages = ["setup", "rising", "climax", "resolved"]
    if new_stage not in valid_stages:
        return {"error": f"Invalid stage: {new_stage}"}

    arc["stage"] = new_stage
    if new_stage == "resolved":
        arc["status"] = "resolved"
    else:
        arc["status"] = new_stage

    save_arc(arc["world_id"], arc)
    logger.info(f"Arc advanced | arc_id={arc_id} | stage={new_stage}")
    return arc


def resolve_arc(arc_id: str, resolution_id: str) -> dict:
    """
    Resolves a story arc with a specific ending.
    Called when player makes the climax choice.
    """
    arc = load_arc(arc_id)
    if not arc:
        return {"error": "Arc not found"}

    resolutions = arc.get("possible_resolutions", [])
    chosen = next(
        (r for r in resolutions if r.get("id") == resolution_id),
        resolutions[-1] if resolutions else {}
    )

    arc["status"] = "resolved"
    arc["stage"] = "resolved"
    arc["resolution_chosen"] = resolution_id
    arc["resolution_details"] = chosen

    save_arc(arc["world_id"], arc)

    logger.info(
        f"Arc resolved | arc_id={arc_id} | "
        f"resolution={resolution_id}"
    )

    return {
        "arc_id": arc_id,
        "title": arc.get("title"),
        "resolution": chosen,
        "world_impact": chosen.get("world_impact", ""),
        "player_reward": chosen.get("player_reward", ""),
    }