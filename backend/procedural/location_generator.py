import json
import random
from backend.llm_client import chat_completion_json
from backend.procedural.world_context import (
    build_world_context_string,
    build_location_context_string,
)
from backend.procedural.name_generator import generate_location_name
from backend.database.world_store import (
    create_location, get_regions, get_locations,
    get_factions, record_event,
)
from backend.database.db import LocationType
from backend.world_engine.world_clock import get_current_world_time
from backend.logger import get_logger

logger = get_logger("procedural.location")

# Biome → appropriate location types
BIOME_LOCATION_TYPES = {
    "forest": [
        "village", "ruins", "dungeon", "wilderness", "temple"
    ],
    "mountain": [
        "mine", "dungeon", "ruins", "village", "castle"
    ],
    "plains": [
        "city", "village", "market", "castle", "ruins"
    ],
    "desert": [
        "ruins", "dungeon", "village", "temple", "wilderness"
    ],
    "swamp": [
        "ruins", "dungeon", "village", "wilderness", "temple"
    ],
    "coastal": [
        "city", "village", "ruins", "dungeon", "market"
    ],
    "tundra": [
        "ruins", "dungeon", "village", "wilderness", "mine"
    ],
}

# Biome → appropriate resources and features
BIOME_FEATURES = {
    "forest": {
        "resources": ["timber", "herbs", "game", "mushrooms"],
        "dangers": ["bandits", "wolves", "corrupted wildlife", "ancient spirits"],
        "lore_elements": ["druid circles", "elven ruins", "hidden shrines"],
    },
    "mountain": {
        "resources": ["iron ore", "gold", "gemstones", "stone"],
        "dangers": ["trolls", "avalanches", "mountain bandits", "wyverns"],
        "lore_elements": ["dwarven halls", "dragon lairs", "ancient fortresses"],
    },
    "plains": {
        "resources": ["grain", "cattle", "trade goods", "clay"],
        "dangers": ["raiding parties", "war bands", "mercenaries"],
        "lore_elements": ["ancient battlefields", "standing stones", "burial mounds"],
    },
    "desert": {
        "resources": ["gold", "ancient artifacts", "rare spices", "glass"],
        "dangers": ["sandstorms", "scorpions", "desert raiders", "undead"],
        "lore_elements": ["ancient tombs", "buried cities", "oasis temples"],
    },
    "swamp": {
        "resources": ["rare herbs", "alchemical ingredients", "peat"],
        "dangers": ["disease", "bog creatures", "will-o-wisps", "serpents"],
        "lore_elements": ["witch huts", "sunken ruins", "cursed graves"],
    },
    "coastal": {
        "resources": ["fish", "salt", "sea trade", "pearls"],
        "dangers": ["pirates", "sea monsters", "storms", "smugglers"],
        "lore_elements": ["shipwrecks", "sea caves", "lighthouse ruins"],
    },
    "tundra": {
        "resources": ["furs", "mammoth ivory", "ice crystals"],
        "dangers": ["frost giants", "dire wolves", "ice elementals"],
        "lore_elements": ["frozen ruins", "ancient burial mounds", "ice temples"],
    },
}


def generate_location_content(
    world_id: int,
    region_id: int,
    location_type: str,
    terrain_type: str,
    danger_level: int,
    controlling_faction_name: str = None,
) -> dict:
    """
    Uses LLM to generate complete location content
    consistent with world state and biome.
    """
    logger.info(
        f"Generating location | type={location_type} | "
        f"terrain={terrain_type} | danger={danger_level}"
    )

    world_context = build_world_context_string(world_id)
    biome_features = BIOME_FEATURES.get(terrain_type, BIOME_FEATURES["plains"])

    prompt = f"""{world_context}

You are generating a new {location_type} for an RPG world.

Location Context:
- Terrain: {terrain_type}
- Danger Level: {danger_level}/10
- Controlling Faction: {controlling_faction_name or 'None'}
- Available Resources: {', '.join(biome_features['resources'])}
- Common Dangers: {', '.join(biome_features['dangers'])}
- Historical Elements: {', '.join(biome_features['lore_elements'])}

Generate a detailed, consistent location that fits this world and context.

Return ONLY valid JSON:
{{
    "description": "3-4 sentences vividly describing this location",
    "history": "2-3 sentences of this location's history",
    "atmosphere": "1 sentence describing the feel/mood",
    "population": 0-50000,
    "wealth_level": 1-10,
    "safety_level": 1-10,
    "current_events": [
        "one thing currently happening here",
        "another ongoing situation"
    ],
    "rumors": [
        "a rumor circulating here",
        "another rumor players might hear"
    ],
    "points_of_interest": [
        "interesting place within this location",
        "another point of interest"
    ],
    "hidden_secrets": [
        "one secret hidden in this location"
    ],
    "available_services": ["service1", "service2"],
    "encounter_hooks": [
        "a situation that could lead to adventure"
    ]
}}

Make it feel alive and unique. Connect it to the world's current events.
Return valid JSON only."""

    try:
        raw = chat_completion_json(
            messages=[
                {
                    "role": "system",
                    "content": "You are a creative RPG world builder. Return valid JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1200,
        )

        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        content = json.loads(cleaned.strip())
        logger.info("Location content generated successfully")
        return content

    except Exception as e:
        logger.error(f"Location generation failed: {e}")
        return _default_location_content(location_type, terrain_type)


def create_procedural_location(
    world_id: int,
    region_id: int,
    location_type: str = None,
    name: str = None,
    map_x: float = None,
    map_y: float = None,
) -> dict:
    """
    Creates a complete new procedural location:
    1. Determines location type from biome if not specified
    2. Generates a consistent name
    3. Gets controlling faction context
    4. Generates full location content with LLM
    5. Saves to database
    6. Records creation event
    """
    # Get region info for context
    regions = get_regions(world_id)
    region = next((r for r in regions if r.id == region_id), None)
    if not region:
        raise ValueError(f"Region {region_id} not found")

    terrain = region.terrain_type
    danger = region.danger_level

    # Determine location type from biome if not specified
    if not location_type:
        biome_types = BIOME_LOCATION_TYPES.get(
            terrain, BIOME_LOCATION_TYPES["plains"]
        )
        location_type = random.choice(biome_types)

    # Generate name if not provided
    if not name:
        culture = _get_culture_for_terrain(terrain)
        name = generate_location_name(
            terrain=terrain,
            location_type=location_type,
            culture=culture,
            seed=f"{world_id}_{region_id}_{random.randint(1000, 9999)}",
        )

    # Get controlling faction
    factions = get_factions(world_id)
    controlling_faction = None
    if factions and random.random() > 0.4:
        controlling_faction = random.choice(factions)

    # Generate location content
    content = generate_location_content(
        world_id=world_id,
        region_id=region_id,
        location_type=location_type,
        terrain_type=terrain,
        danger_level=danger,
        controlling_faction_name=(
            controlling_faction.name if controlling_faction else None
        ),
    )

    # Determine map position
    if map_x is None:
        map_x = region.map_x + random.uniform(-15, 15)
        map_x = max(0, min(100, map_x))
    if map_y is None:
        map_y = region.map_y + random.uniform(-15, 15)
        map_y = max(0, min(100, map_y))

    # Save to database
    location = create_location(
        region_id=region_id,
        name=name,
        location_type=location_type,
        description=content.get("description", ""),
        population=content.get("population", 0),
        wealth_level=content.get("wealth_level", 5),
        safety_level=content.get("safety_level", 5),
        map_x=map_x,
        map_y=map_y,
        history=content.get("history", ""),
    )

    # Add rumors and current events
    from backend.database.db import SessionLocal, Location as LocationModel
    db = SessionLocal()
    try:
        loc_record = db.query(LocationModel).filter(
            LocationModel.id == location.id
        ).first()
        if loc_record:
            loc_record.current_events = json.dumps(
                content.get("current_events", [])
            )
            loc_record.rumors = json.dumps(
                content.get("rumors", [])
            )
            db.commit()
    finally:
        db.close()

    # Record discovery event
    world_time = get_current_world_time(world_id)
    record_event(
        world_id=world_id,
        event_type="discovery",
        title=f"{name} Discovered",
        description=(
            f"A new {location_type} called {name} has been "
            f"revealed in the {region.name} region."
        ),
        world_day=world_time.get("total_days", 0.0),
        region_id=region_id,
        location_id=location.id,
        is_notable=False,
        importance=2,
    )

    logger.info(
        f"Procedural location created | "
        f"name='{name}' | type={location_type} | id={location.id}"
    )

    return {
        "id": location.id,
        "name": name,
        "type": location_type,
        "region": region.name,
        "terrain": terrain,
        "description": content.get("description", ""),
        "atmosphere": content.get("atmosphere", ""),
        "history": content.get("history", ""),
        "population": content.get("population", 0),
        "wealth_level": content.get("wealth_level", 5),
        "safety_level": content.get("safety_level", 5),
        "current_events": content.get("current_events", []),
        "rumors": content.get("rumors", []),
        "points_of_interest": content.get("points_of_interest", []),
        "hidden_secrets": content.get("hidden_secrets", []),
        "available_services": content.get("available_services", []),
        "encounter_hooks": content.get("encounter_hooks", []),
        "map_x": map_x,
        "map_y": map_y,
    }


def generate_complete_dungeon(
    world_id: int,
    region_id: int,
    danger_level: int = None,
    theme: str = None,
) -> dict:
    """
    Generates a complete dungeon with:
    - Main entrance location
    - Multiple floors/areas
    - Boss encounter
    - Unique treasure
    - Lore connected to world history
    """
    logger.info(
        f"Generating complete dungeon | world_id={world_id}"
    )

    regions = get_regions(world_id)
    region = next((r for r in regions if r.id == region_id), None)
    if not region:
        raise ValueError(f"Region {region_id} not found")

    terrain = region.terrain_type
    if danger_level is None:
        danger_level = region.danger_level + random.randint(-1, 2)
        danger_level = max(1, min(10, danger_level))

    world_context = build_world_context_string(world_id)

    prompt = f"""{world_context}

Generate a complete dungeon for a {terrain} region.
Danger Level: {danger_level}/10
Theme preference: {theme or 'match the world and terrain'}

Return ONLY valid JSON:
{{
    "name": "Dungeon name",
    "type": "catacombs|cave|ruins|fortress|tomb|laboratory|temple",
    "description": "3-4 sentences describing the dungeon entrance and exterior",
    "lore": "3-4 sentences of dungeon history connected to the world",
    "atmosphere": "The overall feel: dark, mysterious, ancient, etc.",
    "floors": [
        {{
            "floor_number": 1,
            "name": "Floor name",
            "description": "What this floor looks like",
            "enemies": ["enemy type 1", "enemy type 2"],
            "hazards": ["environmental hazard"],
            "treasures": ["item or treasure found here"],
            "secret": "hidden thing on this floor"
        }}
    ],
    "boss": {{
        "name": "Boss name",
        "type": "creature type",
        "description": "Boss appearance and personality",
        "abilities": ["ability 1", "ability 2"],
        "weakness": "how to defeat them",
        "lore": "why this boss is here"
    }},
    "final_treasure": {{
        "name": "Unique item name",
        "type": "weapon|armor|artifact|spellbook",
        "description": "What this item looks like",
        "power": "What it does",
        "lore": "Its history in the world"
    }},
    "quest_hooks": [
        "a reason to enter this dungeon"
    ]
}}

Create exactly 3 floors.
Make everything connected to the world's current state and history.
Return valid JSON only."""

    try:
        raw = chat_completion_json(
            messages=[
                {
                    "role": "system",
                    "content": "You are a creative dungeon designer. Return valid JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
        )

        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        dungeon_data = json.loads(cleaned.strip())

        # Create the dungeon as a location
        name = dungeon_data.get(
            "name",
            generate_location_name(
                terrain=terrain,
                location_type="dungeon",
                culture="dark",
            )
        )

        location = create_location(
            region_id=region_id,
            name=name,
            location_type="dungeon",
            description=dungeon_data.get("description", ""),
            population=0,
            wealth_level=danger_level,
            safety_level=max(1, 11 - danger_level),
            history=dungeon_data.get("lore", ""),
        )

        world_time = get_current_world_time(world_id)
        record_event(
            world_id=world_id,
            event_type="discovery",
            title=f"Dungeon Discovered: {name}",
            description=(
                f"Adventurers have located {name}, "
                f"a dangerous {dungeon_data.get('type', 'dungeon')} "
                f"in {region.name}."
            ),
            world_day=world_time.get("total_days", 0.0),
            region_id=region_id,
            location_id=location.id,
            is_notable=True,
            importance=4,
        )

        dungeon_data["location_id"] = location.id
        dungeon_data["region"] = region.name
        dungeon_data["danger_level"] = danger_level

        logger.info(
            f"Dungeon generated | name='{name}' | "
            f"floors={len(dungeon_data.get('floors', []))}"
        )
        return dungeon_data

    except Exception as e:
        logger.error(f"Dungeon generation failed: {e}", exc_info=True)
        raise


def _get_culture_for_terrain(terrain: str) -> str:
    mapping = {
        "forest": "elven",
        "mountain": "dwarven",
        "coastal": "coastal",
        "plains": "human",
        "desert": "human",
        "swamp": "dark",
        "tundra": "human",
    }
    return mapping.get(terrain, "human")


def _default_location_content(
    location_type: str,
    terrain: str,
) -> dict:
    return {
        "description": (
            f"A {location_type} situated in the {terrain} landscape. "
            f"The air here carries the weight of history and danger."
        ),
        "history": (
            f"This {location_type} has stood for generations, "
            f"witnessing the rise and fall of many powers."
        ),
        "atmosphere": "Tense and mysterious",
        "population": 0 if location_type == "dungeon" else 500,
        "wealth_level": 5,
        "safety_level": 5,
        "current_events": [
            "Travelers have been passing through recently",
        ],
        "rumors": [
            "Strange things have been seen nearby at night",
        ],
        "points_of_interest": ["A notable landmark"],
        "hidden_secrets": ["Something is not as it seems here"],
        "available_services": ["basic supplies"],
        "encounter_hooks": ["A stranger approaches you"],
    }