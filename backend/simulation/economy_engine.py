import json
import random
from backend.database.db import SessionLocal, Faction
from backend.database.world_store import (
    get_world, get_factions, get_regions,
    get_locations, get_recent_events,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.logger import get_logger

logger = get_logger("simulation.economy")

# Base prices for common goods (in gold)
BASE_PRICES = {
    "bread": 2,
    "meat": 8,
    "vegetables": 3,
    "ale": 5,
    "wine": 15,
    "iron_ore": 20,
    "steel_ingot": 45,
    "timber": 10,
    "cloth": 12,
    "leather": 18,
    "herbs": 25,
    "potion_health": 50,
    "sword": 80,
    "armor": 150,
    "shield": 60,
    "bow": 45,
    "arrow_bundle": 8,
    "horse": 200,
    "gem_common": 100,
    "gem_rare": 800,
    "spice": 40,
    "silk": 120,
}

# How each world event type affects commodity prices
EVENT_PRICE_EFFECTS = {
    "at_war": {
        "sword": 1.8,
        "armor": 1.7,
        "shield": 1.6,
        "bow": 1.5,
        "arrow_bundle": 1.9,
        "bread": 1.4,
        "meat": 1.5,
        "horse": 1.6,
        "silk": 0.6,
        "gem_common": 0.7,
        "wine": 0.8,
    },
    "trade_route_open": {
        "spice": 0.7,
        "silk": 0.75,
        "gem_common": 0.8,
        "gem_rare": 0.75,
        "cloth": 0.85,
    },
    "drought": {
        "bread": 2.5,
        "vegetables": 2.2,
        "meat": 1.8,
        "ale": 1.4,
        "herbs": 1.6,
    },
    "plague": {
        "potion_health": 3.0,
        "herbs": 2.5,
        "cloth": 0.5,
        "silk": 0.4,
    },
    "rich_mine_discovered": {
        "iron_ore": 0.6,
        "steel_ingot": 0.65,
        "gem_common": 0.7,
    },
    "merchant_guild_strong": {
        "spice": 0.85,
        "silk": 0.9,
        "cloth": 0.88,
        "wine": 0.9,
    },
    "cult_influence_high": {
        "herbs": 1.3,
        "gem_rare": 1.4,
        "potion_health": 1.2,
    },
}

# Seasonal price effects
SEASON_EFFECTS = {
    "spring": {
        "bread": 0.9,
        "vegetables": 0.8,
        "herbs": 0.85,
        "timber": 0.95,
    },
    "summer": {
        "bread": 0.85,
        "vegetables": 0.75,
        "ale": 0.9,
        "herbs": 0.8,
    },
    "autumn": {
        "bread": 0.95,
        "vegetables": 0.9,
        "ale": 0.85,
        "timber": 0.9,
    },
    "winter": {
        "bread": 1.4,
        "vegetables": 1.6,
        "timber": 1.5,
        "ale": 1.2,
        "meat": 1.3,
        "herbs": 1.4,
    },
}


def calculate_world_price_modifiers(world_id: int) -> dict:
    """
    Calculates price modifiers based on:
    1. Active faction wars and relations
    2. Recent world events
    3. Current season
    4. Faction economic power

    Returns multiplier per commodity (1.0 = base price).
    """
    logger.debug(f"Calculating price modifiers | world_id={world_id}")

    world = get_world(world_id)
    if not world:
        return {}

    modifiers = {commodity: 1.0 for commodity in BASE_PRICES}
    world_time = get_current_world_time(world_id)
    season = world_time.get("season", "spring")

    # Apply season effects
    season_mods = SEASON_EFFECTS.get(season, {})
    for commodity, mod in season_mods.items():
        if commodity in modifiers:
            modifiers[commodity] *= mod

    # Apply faction war effects
    db = SessionLocal()
    try:
        from backend.database.db import FactionRelationship
        wars = db.query(FactionRelationship).filter(
            FactionRelationship.world_id == world_id,
            FactionRelationship.relation == "at_war",
        ).count()

        if wars > 0:
            war_mods = EVENT_PRICE_EFFECTS["at_war"]
            for commodity, mod in war_mods.items():
                if commodity in modifiers:
                    modifiers[commodity] *= (
                        1 + (mod - 1) * min(wars, 3) / 3
                    )

        # Check merchant guild strength
        factions = db.query(Faction).filter(
            Faction.world_id == world_id,
            Faction.faction_type.in_(["guild", "merchant_company"]),
        ).all()

        for faction in factions:
            if faction.political_influence > 70:
                guild_mods = EVENT_PRICE_EFFECTS["merchant_guild_strong"]
                for commodity, mod in guild_mods.items():
                    if commodity in modifiers:
                        modifiers[commodity] *= mod

        # Check cult influence
        cults = db.query(Faction).filter(
            Faction.world_id == world_id,
            Faction.faction_type == "cult",
        ).all()

        for cult in cults:
            if cult.political_influence > 50:
                cult_mods = EVENT_PRICE_EFFECTS["cult_influence_high"]
                for commodity, mod in cult_mods.items():
                    if commodity in modifiers:
                        modifiers[commodity] *= mod

    finally:
        db.close()

    # Apply recent event effects
    recent_events = get_recent_events(
        world_id, limit=10, notable_only=True
    )
    for event in recent_events:
        desc_lower = event.description.lower()
        if any(
            word in desc_lower
            for word in ["drought", "famine", "crops failed"]
        ):
            drought_mods = EVENT_PRICE_EFFECTS["drought"]
            for commodity, mod in drought_mods.items():
                if commodity in modifiers:
                    modifiers[commodity] *= mod
            break

        if "plague" in desc_lower or "disease" in desc_lower:
            plague_mods = EVENT_PRICE_EFFECTS["plague"]
            for commodity, mod in plague_mods.items():
                if commodity in modifiers:
                    modifiers[commodity] *= mod
            break

    # Add small random noise (market volatility)
    for commodity in modifiers:
        noise = random.uniform(0.95, 1.05)
        modifiers[commodity] *= noise
        modifiers[commodity] = round(modifiers[commodity], 3)

    logger.debug(
        f"Price modifiers calculated | "
        f"season={season} | wars={wars if 'wars' in dir() else 0}"
    )
    return modifiers


def get_current_prices(world_id: int) -> dict:
    """
    Returns current prices for all commodities
    with modifiers applied.
    """
    modifiers = calculate_world_price_modifiers(world_id)
    prices = {}

    for commodity, base_price in BASE_PRICES.items():
        modifier = modifiers.get(commodity, 1.0)
        current_price = max(1, int(base_price * modifier))
        prices[commodity] = {
            "base_price": base_price,
            "current_price": current_price,
            "modifier": round(modifier, 3),
            "price_trend": _get_trend(modifier),
        }

    return prices


def _get_trend(modifier: float) -> str:
    if modifier >= 1.5:
        return "very_high"
    elif modifier >= 1.2:
        return "high"
    elif modifier >= 0.9:
        return "normal"
    elif modifier >= 0.7:
        return "low"
    else:
        return "very_low"


def process_trade(
    world_id: int,
    player_id: int,
    commodity: str,
    quantity: int,
    is_buying: bool,
    location_id: int = None,
) -> dict:
    """
    Processes a player trade transaction.
    Updates player gold based on current market prices.

    is_buying: True = player buys (loses gold)
               False = player sells (gains gold)
    """
    if commodity not in BASE_PRICES:
        return {"error": f"Unknown commodity: {commodity}"}

    prices = get_current_prices(world_id)
    price_info = prices.get(commodity, {})
    unit_price = price_info.get("current_price", BASE_PRICES[commodity])

    # Sell price is 60% of buy price (merchant markup)
    if not is_buying:
        unit_price = int(unit_price * 0.6)

    total_cost = unit_price * quantity

    db = SessionLocal()
    try:
        from backend.database.db import Player
        player = db.query(Player).filter(
            Player.id == player_id
        ).first()

        if not player:
            return {"error": "Player not found"}

        if is_buying and player.gold < total_cost:
            return {
                "error": "Insufficient gold",
                "required": total_cost,
                "available": player.gold,
            }

        # Process transaction
        if is_buying:
            player.gold -= total_cost
        else:
            player.gold += total_cost

        db.commit()

        logger.info(
            f"Trade processed | "
            f"player={player_id} | "
            f"commodity={commodity} | "
            f"qty={quantity} | "
            f"{'bought' if is_buying else 'sold'} | "
            f"total={total_cost}g"
        )

        return {
            "success": True,
            "commodity": commodity,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_cost": total_cost,
            "transaction_type": "purchase" if is_buying else "sale",
            "new_gold": player.gold,
            "price_trend": price_info.get("price_trend", "normal"),
        }

    finally:
        db.close()