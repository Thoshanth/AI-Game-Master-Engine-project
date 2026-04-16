import json
from pathlib import Path
from datetime import datetime
from backend.simulation.economy_engine import (
    get_current_prices, BASE_PRICES,
)
from backend.database.world_store import get_locations, get_regions
from backend.logger import get_logger

logger = get_logger("simulation.market")

MARKET_DATA_PATH = Path("game_data/markets")
MARKET_DATA_PATH.mkdir(parents=True, exist_ok=True)


def get_location_market(
    world_id: int,
    location_id: int,
) -> dict:
    """
    Returns the market prices for a specific location.
    Different locations have different available goods
    based on their type and region resources.
    """
    prices = get_current_prices(world_id)

    # Determine which goods are available at this location
    available_goods = _get_available_goods(location_id, world_id)

    market = {
        "location_id": location_id,
        "world_id": world_id,
        "last_updated": datetime.utcnow().isoformat(),
        "goods": {},
    }

    for commodity in available_goods:
        if commodity in prices:
            market["goods"][commodity] = prices[commodity]

    return market


def get_world_economy_report(world_id: int) -> dict:
    """
    Returns a complete economy report for the world.
    Shows all prices, trends, and economic indicators.
    """
    prices = get_current_prices(world_id)

    # Find biggest price changes
    high_prices = {
        k: v for k, v in prices.items()
        if v["price_trend"] in ["high", "very_high"]
    }
    low_prices = {
        k: v for k, v in prices.items()
        if v["price_trend"] in ["low", "very_low"]
    }

    # Trading opportunities
    opportunities = []
    for commodity, price_data in prices.items():
        if price_data["modifier"] >= 1.3:
            opportunities.append({
                "commodity": commodity,
                "opportunity": "sell",
                "reason": f"Price is {int((price_data['modifier']-1)*100)}% above normal",
                "current_price": price_data["current_price"],
            })
        elif price_data["modifier"] <= 0.75:
            opportunities.append({
                "commodity": commodity,
                "opportunity": "buy",
                "reason": f"Price is {int((1-price_data['modifier'])*100)}% below normal",
                "current_price": price_data["current_price"],
            })

    return {
        "world_id": world_id,
        "total_commodities": len(prices),
        "prices": prices,
        "inflated_goods": list(high_prices.keys()),
        "deflated_goods": list(low_prices.keys()),
        "trading_opportunities": sorted(
            opportunities,
            key=lambda x: abs(1 - prices[x["commodity"]]["modifier"]),
            reverse=True,
        )[:5],
        "economic_summary": _build_economic_summary(prices),
    }


def _get_available_goods(
    location_id: int,
    world_id: int,
) -> list[str]:
    """
    Returns goods available at a location based on its type.
    """
    from backend.database.world_store import get_location
    location = get_location(location_id)

    if not location:
        return list(BASE_PRICES.keys())[:10]

    location_type = location.location_type

    goods_by_type = {
        "city": list(BASE_PRICES.keys()),
        "market": list(BASE_PRICES.keys()),
        "village": [
            "bread", "vegetables", "meat", "ale",
            "timber", "leather", "herbs", "cloth",
        ],
        "tavern": [
            "bread", "meat", "ale", "wine",
            "potion_health",
        ],
        "mine": [
            "iron_ore", "steel_ingot", "gem_common",
            "gem_rare", "timber",
        ],
        "dungeon": [],
        "castle": [
            "sword", "armor", "shield", "bow",
            "arrow_bundle", "horse",
        ],
        "temple": [
            "herbs", "potion_health", "gem_rare",
            "cloth", "wine",
        ],
        "ruins": [],
        "wilderness": [
            "herbs", "leather", "meat", "timber",
        ],
    }

    return goods_by_type.get(
        location_type,
        list(BASE_PRICES.keys())[:8],
    )


def _build_economic_summary(prices: dict) -> str:
    """Builds a readable economic summary."""
    high_count = sum(
        1 for p in prices.values()
        if p["price_trend"] in ["high", "very_high"]
    )
    low_count = sum(
        1 for p in prices.values()
        if p["price_trend"] in ["low", "very_low"]
    )

    if high_count > len(prices) * 0.4:
        return "Inflation is high — prices are elevated across the board"
    elif low_count > len(prices) * 0.4:
        return "Deflation — prices are low, good time to stock up"
    elif prices.get("sword", {}).get("modifier", 1) > 1.4:
        return "War economy — military goods are expensive, luxury goods are cheap"
    else:
        return "Stable economy with normal price fluctuations"