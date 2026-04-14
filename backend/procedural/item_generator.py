import json
import random
from backend.llm_client import chat_completion_json
from backend.procedural.world_context import build_world_context_string
from backend.procedural.name_generator import generate_item_name
from backend.database.world_store import record_event, get_world
from backend.world_engine.world_clock import get_current_world_time
from backend.logger import get_logger

logger = get_logger("procedural.item")

RARITY_WEIGHTS = {
    "common": 50,
    "uncommon": 30,
    "rare": 15,
    "legendary": 5,
}

RARITY_VALUE_RANGES = {
    "common": (1, 50),
    "uncommon": (50, 300),
    "rare": (300, 2000),
    "legendary": (2000, 20000),
}


def generate_item_with_lore(
    world_id: int,
    item_type: str = None,
    rarity: str = None,
    location_context: str = None,
) -> dict:
    """
    Generates an item whose lore is connected to world history.

    A sword found in ancient ruins has a story connected to
    the faction that built those ruins. A potion found in a
    plague town has properties that reference the plague.

    Items feel like they belong to THIS world, not a generic fantasy.
    """
    if not item_type:
        item_type = random.choice(
            ["weapon", "armor", "potion", "artifact", "tool", "key"]
        )

    if not rarity:
        rarities = list(RARITY_WEIGHTS.keys())
        weights = list(RARITY_WEIGHTS.values())
        rarity = random.choices(rarities, weights=weights)[0]

    world_context = build_world_context_string(world_id)
    value_min, value_max = RARITY_VALUE_RANGES[rarity]

    prompt = f"""{world_context}

Generate a {rarity} {item_type} that belongs to this specific world.
{f'Found in: {location_context}' if location_context else ''}

The item's lore MUST connect to the world's history, factions, or current events.
A common item has simple backstory. A legendary item has epic world-changing history.

Return ONLY valid JSON:
{{
    "name": "Item name",
    "type": "{item_type}",
    "rarity": "{rarity}",
    "description": "2-3 sentences describing appearance",
    "lore": "2-4 sentences connecting this item to world history or current events",
    "properties": {{
        "primary_stat": "main mechanical property",
        "secondary_stat": "optional secondary property",
        "special_ability": "unique ability if rare or legendary, null otherwise"
    }},
    "value": {value_min}-{value_max},
    "weight": 0.1-20.0,
    "cursed": false,
    "quest_relevance": "Is this connected to any quest? If so how?",
    "previous_owner": "Who last owned this and what happened to them?"
}}

Return valid JSON only."""

    try:
        raw = chat_completion_json(
            messages=[
                {
                    "role": "system",
                    "content": "You are an RPG item designer. Return valid JSON only."
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

        item_data = json.loads(cleaned.strip())
        logger.info(
            f"Item generated | name='{item_data.get('name')}' | "
            f"rarity={rarity} | type={item_type}"
        )
        return item_data

    except Exception as e:
        logger.error(f"Item generation failed: {e}")
        return {
            "name": generate_item_name(item_type, rarity),
            "type": item_type,
            "rarity": rarity,
            "description": f"A {rarity} {item_type} of unknown origin.",
            "lore": "Its history has been lost to time.",
            "properties": {
                "primary_stat": "standard",
                "secondary_stat": None,
                "special_ability": None,
            },
            "value": random.randint(value_min, value_max),
            "weight": random.uniform(0.5, 5.0),
            "cursed": False,
            "quest_relevance": "None known",
            "previous_owner": "Unknown",
        }


def generate_treasure_hoard(
    world_id: int,
    danger_level: int = 5,
    location_context: str = None,
) -> list[dict]:
    """
    Generates a treasure hoard appropriate for the danger level.
    Higher danger = better loot, more legendary items.
    """
    logger.info(
        f"Generating treasure hoard | danger={danger_level}"
    )

    # Number of items scales with danger
    num_items = random.randint(
        max(1, danger_level - 3),
        danger_level + 2
    )

    # Rarity distribution shifts with danger level
    items = []
    for _ in range(num_items):
        # Higher danger = higher chance of rare items
        if danger_level >= 8 and random.random() < 0.3:
            rarity = "legendary"
        elif danger_level >= 5 and random.random() < 0.4:
            rarity = "rare"
        elif danger_level >= 3 and random.random() < 0.5:
            rarity = "uncommon"
        else:
            rarity = "common"

        item_type = random.choice(
            ["weapon", "armor", "potion", "artifact"]
        )
        item = generate_item_with_lore(
            world_id=world_id,
            item_type=item_type,
            rarity=rarity,
            location_context=location_context,
        )
        items.append(item)

    logger.info(
        f"Treasure hoard generated | items={len(items)}"
    )
    return items