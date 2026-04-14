import json
import random
from backend.llm_client import chat_completion_json
from backend.procedural.world_context import build_world_context_string
from backend.database.world_store import (
    get_factions, get_regions, record_event,
    update_global_state, get_world,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.logger import get_logger

logger = get_logger("procedural.events")

# Event types that can spawn based on world conditions
EVENT_TEMPLATES = {
    "faction_conflict": {
        "trigger": "two factions have hostile relations",
        "types": [
            "border skirmish", "assassination attempt",
            "trade embargo", "propaganda campaign",
            "spy network discovered",
        ],
    },
    "economic": {
        "trigger": "wealth inequality or trade disruption",
        "types": [
            "merchant caravan attacked", "new trade route opened",
            "resource discovered", "market crash",
            "smuggling ring exposed",
        ],
    },
    "natural": {
        "trigger": "seasonal or random",
        "types": [
            "harsh winter storms", "drought affecting crops",
            "magical anomaly detected", "ancient ruins uncovered",
            "plague spreading in region",
        ],
    },
    "political": {
        "trigger": "power vacuum or leadership change",
        "types": [
            "noble house rivalry", "election corruption",
            "succession crisis", "rebel faction emerges",
            "foreign power makes demands",
        ],
    },
    "mysterious": {
        "trigger": "random or hidden faction action",
        "types": [
            "villagers disappearing", "strange lights at night",
            "ancient prophecy discovered", "monster sightings increase",
            "cursed artifact surfaces",
        ],
    },
}


def generate_world_event(
    world_id: int,
    event_category: str = None,
    location_id: int = None,
    region_id: int = None,
    faction_id: int = None,
) -> dict:
    """
    Generates a world event consistent with current world state.

    The event:
    - Connects to existing factions and their goals
    - References real locations in the world
    - Has consequences that ripple into future events
    - Creates potential quest hooks for players
    """
    logger.info(
        f"Generating world event | category={event_category}"
    )

    world_context = build_world_context_string(world_id)
    world_time = get_current_world_time(world_id)

    # Choose event category if not specified
    if not event_category:
        event_category = random.choice(
            list(EVENT_TEMPLATES.keys())
        )

    template = EVENT_TEMPLATES.get(
        event_category, EVENT_TEMPLATES["mysterious"]
    )
    event_type_hint = random.choice(template["types"])

    prompt = f"""{world_context}

Generate a world event that is happening right now in this world.
Event category: {event_category}
Event type hint: {event_type_hint}
Current world day: {world_time.get('total_days', 0):.1f}

The event must:
1. Feel like a natural consequence of the world's current state
2. Reference real factions, tensions, or recent events from the context
3. Create ripple effects that will affect the world going forward
4. Provide potential adventure hooks for players

Return ONLY valid JSON:
{{
    "title": "Event title (short, dramatic)",
    "description": "3-4 sentences describing what is happening",
    "category": "{event_category}",
    "type": "specific type of event",
    "severity": "minor|moderate|major|catastrophic",
    "affected_factions": ["faction names involved"],
    "immediate_consequences": [
        "what happens immediately as a result"
    ],
    "long_term_consequences": [
        "what might happen in the future because of this"
    ],
    "quest_hooks": [
        "adventure opportunity this creates"
    ],
    "rumors_generated": [
        "what people are saying about this event"
    ],
    "world_state_changes": {{
        "economic_impact": "none|minor|moderate|severe",
        "political_impact": "none|minor|moderate|severe",
        "military_impact": "none|minor|moderate|severe"
    }},
    "is_notable": true,
    "importance": 1-10
}}

Return valid JSON only."""

    try:
        raw = chat_completion_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a world events generator for an RPG. "
                        "Return valid JSON only."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
        )

        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        event_data = json.loads(cleaned.strip())

        # Record in database
        db_event = record_event(
            world_id=world_id,
            event_type="world_event",
            title=event_data.get("title", "Unknown Event"),
            description=event_data.get("description", ""),
            world_day=world_time.get("total_days", 0.0),
            location_id=location_id,
            region_id=region_id,
            faction_id=faction_id,
            consequences=event_data.get("immediate_consequences", []),
            is_notable=event_data.get("is_notable", True),
            importance=event_data.get("importance", 5),
        )

        event_data["event_id"] = db_event.id
        event_data["world_day"] = world_time.get("total_days", 0.0)

        logger.info(
            f"World event generated | "
            f"title='{event_data.get('title')}' | "
            f"severity={event_data.get('severity')}"
        )
        return event_data

    except Exception as e:
        logger.error(f"Event generation failed: {e}", exc_info=True)
        raise


def run_autonomous_world_tick(world_id: int) -> list[dict]:
    """
    Runs one world tick — generates events that happen
    automatically as the world evolves.

    Called by the scheduler every N minutes.
    The world keeps moving even when players are offline.

    Returns list of events that occurred.
    """
    logger.info(f"World tick | world_id={world_id}")

    events_generated = []

    # Probability of each event type per tick
    event_chances = [
        ("economic", 0.3),
        ("faction_conflict", 0.25),
        ("mysterious", 0.25),
        ("natural", 0.15),
        ("political", 0.2),
    ]

    for category, probability in event_chances:
        if random.random() < probability:
            try:
                event = generate_world_event(
                    world_id=world_id,
                    event_category=category,
                )
                events_generated.append(event)
                logger.info(
                    f"Tick event | category={category} | "
                    f"title='{event.get('title')}'"
                )
            except Exception as e:
                logger.warning(
                    f"Tick event generation failed: {e}"
                )

    logger.info(
        f"World tick complete | events={len(events_generated)}"
    )
    return events_generated