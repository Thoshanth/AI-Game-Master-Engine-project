import json
import random
from backend.llm_client import chat_completion_json
from backend.database.world_store import (
    create_world, create_region, create_location,
    create_npc, create_faction, create_quest,
    record_event, get_world_by_name,
)
from backend.database.db import (
    TerrainType, LocationType, NPCRole, QuestState
)
from backend.logger import get_logger

logger = get_logger("world_engine.builder")


def generate_world_concept(world_name: str, theme: str) -> dict:
    """
    Uses LLM to generate a complete world concept.
    Returns world description, regions, factions as JSON.
    """
    logger.info(f"Generating world concept | name='{world_name}' | theme='{theme}'")

    prompt = f"""You are a world builder for a text RPG game.
Create a detailed world called "{world_name}" with the theme: {theme}

Return ONLY valid JSON:
{{
    "world_description": "2-3 sentence description of the world",
    "history": "Brief world history in 2-3 sentences",
    "regions": [
        {{
            "name": "Region name",
            "description": "1-2 sentences",
            "terrain": "forest|mountain|plains|desert|swamp|coastal|tundra",
            "danger_level": 1-10,
            "resources": ["resource1", "resource2"],
            "map_x": 0-100,
            "map_y": 0-100
        }}
    ],
    "factions": [
        {{
            "name": "Faction name",
            "type": "kingdom|guild|cult|tribe|merchant_company",
            "description": "1-2 sentences about this faction",
            "motto": "Faction motto",
            "wealth": 500-5000,
            "military_strength": 10-500,
            "goals": ["goal1", "goal2"]
        }}
    ],
    "starting_city": {{
        "name": "City name",
        "description": "2-3 sentences describing the starting city",
        "population": 1000-50000,
        "wealth_level": 1-10,
        "safety_level": 1-10,
        "history": "1-2 sentences of city history"
    }}
}}

Create exactly 4 regions and 3 factions.
Make the world feel alive, dark, and interesting.
Return valid JSON only."""

    try:
        raw = chat_completion_json(
            messages=[
                {
                    "role": "system",
                    "content": "You are a creative world builder. Return valid JSON only."
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

        concept = json.loads(cleaned.strip())
        logger.info("World concept generated successfully")
        return concept

    except Exception as e:
        logger.error(f"World concept generation failed: {e}")
        # Return a default world if LLM fails
        return _default_world_concept(world_name)


def generate_npc(
    location_name: str,
    role: str,
    world_theme: str,
    faction_name: str = None,
) -> dict:
    """Uses LLM to generate a detailed NPC."""
    prompt = f"""Create an NPC for a {world_theme} RPG world.
Location: {location_name}
Role: {role}
{f'Faction: {faction_name}' if faction_name else ''}

Return ONLY valid JSON:
{{
    "name": "NPC full name",
    "age": 20-80,
    "gender": "male|female|non-binary",
    "appearance": "2 sentences describing physical appearance",
    "backstory": "2-3 sentences of personal history",
    "personality_summary": "1 sentence personality description",
    "traits": {{
        "openness": 1.0-10.0,
        "conscientiousness": 1.0-10.0,
        "extraversion": 1.0-10.0,
        "agreeableness": 1.0-10.0,
        "neuroticism": 1.0-10.0
    }},
    "secrets": ["one secret this NPC holds"],
    "initial_rumor": "one rumor this NPC knows about the world"
}}

Make this NPC feel like a real person with depth and flaws.
Return valid JSON only."""

    try:
        raw = chat_completion_json(
            messages=[
                {
                    "role": "system",
                    "content": "You are an RPG character designer. Return valid JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
        )

        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        return json.loads(cleaned.strip())

    except Exception as e:
        logger.warning(f"NPC generation failed: {e} — using default")
        return _default_npc(role)


def build_complete_world(
    world_name: str,
    theme: str = "dark fantasy",
) -> dict:
    """
    Builds a complete game world:
    1. Generate world concept with LLM
    2. Create world in database
    3. Create regions
    4. Create starting city location
    5. Create factions
    6. Generate and create NPCs
    7. Create starting quests
    8. Record creation event

    Returns complete world summary.
    """
    logger.info(
        f"Building complete world | name='{world_name}' | theme='{theme}'"
    )

    # Check if world already exists
    existing = get_world_by_name(world_name)
    if existing:
        logger.warning(f"World '{world_name}' already exists")
        from backend.database.world_store import get_world_summary
        return get_world_summary(existing.id)

    # Step 1: Generate world concept
    concept = generate_world_concept(world_name, theme)

    # Step 2: Create world
    world = create_world(
        name=world_name,
        description=concept.get(
            "world_description",
            f"A {theme} world of adventure and mystery."
        ),
        time_ratio=3600.0,
    )
    world_id = world.id

    # Step 3: Create regions
    region_ids = []
    created_regions = concept.get("regions", [])
    logger.info(f"Creating {len(created_regions)} regions")

    for r in created_regions:
        region = create_region(
            world_id=world_id,
            name=r.get("name", "Unknown Region"),
            description=r.get("description", ""),
            terrain_type=r.get("terrain", "plains"),
            danger_level=r.get("danger_level", 1),
            map_x=r.get("map_x", random.uniform(10, 90)),
            map_y=r.get("map_y", random.uniform(10, 90)),
            resources=r.get("resources", []),
        )
        region_ids.append(region.id)

    # Step 4: Create starting city in first region
    starting_city_data = concept.get("starting_city", {})
    starting_region_id = region_ids[0] if region_ids else None

    if starting_region_id:
        starting_city = create_location(
            region_id=starting_region_id,
            name=starting_city_data.get("name", "Aldenmoor"),
            location_type=LocationType.CITY,
            description=starting_city_data.get(
                "description", "A bustling city."
            ),
            population=starting_city_data.get("population", 5000),
            wealth_level=starting_city_data.get("wealth_level", 6),
            safety_level=starting_city_data.get("safety_level", 6),
            map_x=50.0,
            map_y=50.0,
            history=starting_city_data.get("history", ""),
        )

        # Create tavern in starting city
        tavern = create_location(
            region_id=starting_region_id,
            name=f"The {random.choice(['Golden', 'Silver', 'Iron', 'Rusty', 'Broken'])} {random.choice(['Flagon', 'Sword', 'Shield', 'Crown', 'Compass'])}",
            location_type=LocationType.TAVERN,
            description="A warm tavern filled with travelers and locals.",
            population=30,
            wealth_level=4,
            safety_level=7,
            map_x=52.0,
            map_y=51.0,
        )

        # Create market
        market = create_location(
            region_id=starting_region_id,
            name=f"{starting_city_data.get('name', 'Aldenmoor')} Market Square",
            location_type=LocationType.MARKET,
            description="A busy market square where merchants hawk their wares.",
            population=100,
            wealth_level=7,
            safety_level=8,
            map_x=50.0,
            map_y=52.0,
        )

        # Create dungeon near starting city
        dungeon = create_location(
            region_id=starting_region_id,
            name=f"The {random.choice(['Cursed', 'Ancient', 'Forgotten', 'Shadowed'])} {random.choice(['Catacombs', 'Ruins', 'Caverns', 'Vault'])}",
            location_type=LocationType.DUNGEON,
            description="Dark ruins filled with danger and treasure.",
            population=0,
            wealth_level=8,
            safety_level=2,
            map_x=60.0,
            map_y=45.0,
        )

    # Step 5: Create factions
    faction_ids = []
    for f in concept.get("factions", []):
        faction = create_faction(
            world_id=world_id,
            name=f.get("name", "Unknown Faction"),
            faction_type=f.get("type", "guild"),
            description=f.get("description", ""),
            motto=f.get("motto", ""),
            wealth=f.get("wealth", 1000),
            military_strength=f.get("military_strength", 100),
        )
        faction_ids.append(faction.id)

    # Step 6: Generate NPCs for starting city
    logger.info("Generating NPCs for starting city")
    npc_roles = [
        (NPCRole.INNKEEPER, "tavern"),
        (NPCRole.MERCHANT, "market"),
        (NPCRole.BLACKSMITH, "starting city"),
        (NPCRole.GUARD, "starting city"),
        (NPCRole.QUEST_GIVER, "starting city"),
        (NPCRole.MAGE, "starting city"),
    ]

    for role, location_name in npc_roles:
        try:
            npc_data = generate_npc(
                location_name=starting_city_data.get("name", "Aldenmoor"),
                role=role,
                world_theme=theme,
                faction_name=None,
            )

            # Determine location for this NPC
            if role == NPCRole.INNKEEPER:
                npc_location = tavern.id
            elif role == NPCRole.MERCHANT:
                npc_location = market.id
            else:
                npc_location = starting_city.id

            npc = create_npc(
                world_id=world_id,
                location_id=npc_location,
                name=npc_data.get("name", f"Unknown {role}"),
                role=role,
                appearance=npc_data.get("appearance", ""),
                backstory=npc_data.get("backstory", ""),
                age=npc_data.get("age", 30),
                gender=npc_data.get("gender", "neutral"),
                traits=npc_data.get("traits", {}),
            )

            # Store NPC secrets as known_secrets
            from backend.database.db import SessionLocal
            db = SessionLocal()
            try:
                npc_record = db.query(
                    __import__(
                        'backend.database.db', fromlist=['NPC']
                    ).NPC
                ).filter_by(id=npc.id).first()
                if npc_record:
                    npc_record.known_secrets = json.dumps(
                        npc_data.get("secrets", [])
                    )
                    npc_record.known_rumors = json.dumps(
                        [npc_data.get("initial_rumor", "")]
                    )
                    db.commit()
            finally:
                db.close()

            logger.info(f"NPC created | name='{npc.name}' | role={role}")

        except Exception as e:
            logger.error(f"NPC creation failed for {role}: {e}")

    # Step 7: Create starting quests
    logger.info("Creating starting quests")

    create_quest(
        world_id=world_id,
        title="The Missing Merchant",
        description=(
            "A merchant has not returned from the eastern road. "
            "His family fears the worst. Investigate his disappearance "
            "and discover what lurks on the road east of the city."
        ),
        quest_type="side",
        origin_location_id=starting_city.id,
        objectives=[
            {
                "id": 1,
                "description": "Speak to the merchant's family",
                "completed": False,
            },
            {
                "id": 2,
                "description": "Investigate the eastern road",
                "completed": False,
            },
            {
                "id": 3,
                "description": "Find out what happened to the merchant",
                "completed": False,
            },
        ],
        rewards={
            "gold": 150,
            "experience": 200,
            "reputation": {"merchant_guild": 10},
        },
        trigger_conditions={},
    )

    # Update quest state to available
    from backend.database.db import SessionLocal
    db = SessionLocal()
    try:
        quest = db.query(
            __import__('backend.database.db', fromlist=['Quest']).Quest
        ).filter_by(world_id=world_id).first()
        if quest:
            quest.state = QuestState.AVAILABLE
            db.commit()
    finally:
        db.close()

    # Step 8: Record world creation event
    record_event(
        world_id=world_id,
        event_type="world_event",
        title="The World Begins",
        description=(
            f"The world of {world_name} was born. "
            f"Ancient forces stir as the age of adventure begins."
        ),
        world_day=0.0,
        is_notable=True,
        importance=10,
    )

    logger.info(
        f"World '{world_name}' fully built | id={world_id}"
    )

    from backend.database.world_store import get_world_summary
    return get_world_summary(world_id)


def _default_world_concept(world_name: str) -> dict:
    """Fallback world concept if LLM fails."""
    return {
        "world_description": f"{world_name} is a dark fantasy world of ancient kingdoms, forgotten magic, and endless conflict.",
        "history": "Once a land of great empires, now fragmented kingdoms struggle for dominance over ancient ruins.",
        "regions": [
            {
                "name": "The Northern Reaches",
                "description": "Frozen tundra filled with ancient ruins and dangerous beasts.",
                "terrain": "tundra",
                "danger_level": 7,
                "resources": ["iron", "furs"],
                "map_x": 50.0,
                "map_y": 20.0,
            },
            {
                "name": "The Verdant Vale",
                "description": "Rich farmland and dense forests surrounding the starting city.",
                "terrain": "forest",
                "danger_level": 2,
                "resources": ["wood", "food", "herbs"],
                "map_x": 50.0,
                "map_y": 50.0,
            },
            {
                "name": "The Ashwood",
                "description": "A haunted forest where dark magic lingers.",
                "terrain": "forest",
                "danger_level": 6,
                "resources": ["rare herbs", "dark crystals"],
                "map_x": 30.0,
                "map_y": 60.0,
            },
            {
                "name": "The Crimson Desert",
                "description": "A vast desert hiding ancient tombs and deadly creatures.",
                "terrain": "desert",
                "danger_level": 8,
                "resources": ["gold", "ancient artifacts"],
                "map_x": 70.0,
                "map_y": 70.0,
            },
        ],
        "factions": [
            {
                "name": "The Iron Crown",
                "type": "kingdom",
                "description": "The dominant kingdom ruling with an iron fist.",
                "motto": "Order through strength.",
                "wealth": 5000,
                "military_strength": 500,
                "goals": ["expand territory", "crush rebels"],
            },
            {
                "name": "The Shadow Conclave",
                "type": "cult",
                "description": "A secretive organization with dark magical powers.",
                "motto": "Knowledge is power.",
                "wealth": 2000,
                "military_strength": 100,
                "goals": ["obtain ancient artifact", "undermine the Crown"],
            },
            {
                "name": "The Free Merchants Guild",
                "type": "guild",
                "description": "A powerful trading guild that controls commerce.",
                "motto": "Coin opens all doors.",
                "wealth": 8000,
                "military_strength": 50,
                "goals": ["monopolize trade routes", "avoid war"],
            },
        ],
        "starting_city": {
            "name": "Aldenmoor",
            "description": "A bustling city at the crossroads of major trade routes.",
            "population": 8000,
            "wealth_level": 6,
            "safety_level": 6,
            "history": "Founded 300 years ago as a trading post, now a major city.",
        },
    }


def _default_npc(role: str) -> dict:
    """Fallback NPC if LLM fails."""
    names = [
        "Aldric", "Mara", "Theron", "Seris",
        "Venn", "Kira", "Dorn", "Lysa"
    ]
    return {
        "name": random.choice(names),
        "age": random.randint(25, 60),
        "gender": random.choice(["male", "female"]),
        "appearance": f"A weathered {role} with tired eyes and worn clothes.",
        "backstory": f"Has worked as a {role} for many years in this city.",
        "traits": {
            "openness": random.uniform(3, 7),
            "conscientiousness": random.uniform(4, 8),
            "extraversion": random.uniform(3, 7),
            "agreeableness": random.uniform(3, 7),
            "neuroticism": random.uniform(2, 6),
        },
        "secrets": ["Has a troubled past they don't speak about."],
        "initial_rumor": "Strange lights were seen near the old ruins last night.",
    }