import time
from datetime import datetime
from backend.database.world_store import (
    get_world, update_world_time
)
from backend.logger import get_logger

logger = get_logger("world_engine.clock")

SEASONS = ["spring", "summer", "autumn", "winter"]
DAYS_PER_SEASON = 30
DAYS_PER_YEAR = 120


def get_current_world_time(world_id: int) -> dict:
    """
    Calculates the current world time based on
    real elapsed time and the world's time ratio.

    time_ratio = real seconds per world day
    Default: 3600 = 1 real hour = 1 world day
    """
    world = get_world(world_id)
    if not world:
        return {}

    real_elapsed_seconds = (
        datetime.utcnow() - world.real_time_start
    ).total_seconds()

    world_days_elapsed = real_elapsed_seconds / world.time_ratio
    total_world_days = world.world_time_days + world_days_elapsed

    # Calculate year, season, day of season
    year = int(total_world_days // DAYS_PER_YEAR) + 1
    day_of_year = total_world_days % DAYS_PER_YEAR
    season_index = int(day_of_year // DAYS_PER_SEASON) % 4
    season = SEASONS[season_index]
    day_of_season = int(day_of_year % DAYS_PER_SEASON) + 1

    # Calculate time of day (0-24 hours)
    day_fraction = total_world_days % 1.0
    hour_of_day = day_fraction * 24

    # Time of day label
    if 6 <= hour_of_day < 12:
        time_of_day = "morning"
    elif 12 <= hour_of_day < 17:
        time_of_day = "afternoon"
    elif 17 <= hour_of_day < 21:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    return {
        "total_days": round(total_world_days, 4),
        "year": year,
        "season": season,
        "day_of_season": day_of_season,
        "hour_of_day": round(hour_of_day, 2),
        "time_of_day": time_of_day,
        "time_string": (
            f"Year {year}, {season.title()} Day {day_of_season}, "
            f"{time_of_day.title()}"
        ),
    }


def sync_world_clock(world_id: int):
    """
    Syncs the world clock to the database.
    Called periodically by the scheduler.
    """
    world_time = get_current_world_time(world_id)
    if world_time:
        update_world_time(
            world_id,
            world_time["total_days"],
            world_time["season"],
        )
        logger.debug(
            f"Clock synced | world_id={world_id} | "
            f"time='{world_time['time_string']}'"
        )


def get_npc_current_activity(hour_of_day: float, schedule: dict) -> str:
    """
    Returns what an NPC should be doing at the current hour
    based on their schedule.
    """
    current_hour = int(hour_of_day)

    # Find the most recent scheduled activity
    activity = "sleeping"
    for hour_str, act in sorted(schedule.items(), key=lambda x: int(x[0])):
        if int(hour_str) <= current_hour:
            activity = act

    return activity