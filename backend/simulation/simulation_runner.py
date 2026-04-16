import json
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.simulation.faction_agent import (
    run_faction_turn, update_faction_relations,
)
from backend.simulation.economy_engine import calculate_world_price_modifiers
from backend.database.world_store import (
    get_all_worlds, get_factions, record_event,
)
from backend.world_engine.world_clock import (
    get_current_world_time, sync_world_clock,
)
from backend.narrative.narrative_pipeline import run_narrative_tick
from backend.logger import get_logger

logger = get_logger("simulation.runner")

SIMULATION_LOG_PATH = Path("game_data/simulation_log.json")

# Global scheduler instance
scheduler = AsyncIOScheduler()
_active_world_ids: set[int] = set()


def _load_simulation_log() -> list:
    if SIMULATION_LOG_PATH.exists():
        with open(SIMULATION_LOG_PATH) as f:
            return json.load(f)
    return []


def _save_simulation_log(log: list):
    SIMULATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SIMULATION_LOG_PATH, "w") as f:
        json.dump(log[-100:], f, indent=2)


async def run_simulation_tick(world_id: int) -> dict:
    """
    The master simulation tick. Runs everything for one world:

    1. Sync world clock
    2. Run each faction's autonomous turn
    3. Update faction relations
    4. Recalculate economy prices
    5. Run narrative tick (arc advancement, emotions)
    6. Broadcast notable events to connected players
    7. Log tick results

    In production: runs every 15 minutes via APScheduler.
    Manual trigger available via API for testing.
    """
    tick_start = datetime.utcnow()
    logger.info(
        f"Simulation tick starting | world_id={world_id}"
    )

    tick_result = {
        "world_id": world_id,
        "tick_time": tick_start.isoformat(),
        "faction_actions": [],
        "relation_changes": [],
        "economy_updated": False,
        "narrative_changes": {},
        "errors": [],
    }

    # Step 1: Sync world clock
    try:
        sync_world_clock(world_id)
        world_time = get_current_world_time(world_id)
        tick_result["world_day"] = world_time.get("total_days", 0)
        tick_result["world_time"] = world_time.get("time_string")
    except Exception as e:
        logger.error(f"Clock sync failed: {e}")
        tick_result["errors"].append(f"clock_sync: {e}")

    # Step 2: Run each faction's turn
    factions = get_factions(world_id)
    for faction in factions:
        try:
            action_result = run_faction_turn(world_id, faction.id)
            if action_result:
                tick_result["faction_actions"].append(action_result)

                # Broadcast notable faction actions
                if action_result.get("is_notable"):
                    try:
                        from backend.multiplayer.world_sync import (
                            sync_world_event_to_all,
                        )
                        await sync_world_event_to_all(
                            world_id=world_id,
                            event_title=f"{action_result['faction_name']}: {action_result['action_taken'].replace('_', ' ').title()}",
                            event_description=action_result.get(
                                "description", ""
                            ),
                            severity="moderate",
                        )
                    except Exception as e:
                        logger.warning(f"Broadcast failed: {e}")

        except Exception as e:
            logger.warning(
                f"Faction turn failed | "
                f"faction_id={faction.id}: {e}"
            )
            tick_result["errors"].append(
                f"faction_{faction.id}: {e}"
            )

    # Step 3: Update faction relations
    try:
        relation_changes = update_faction_relations(world_id)
        tick_result["relation_changes"] = relation_changes

        # Broadcast major relation changes
        for change in relation_changes:
            if change.get("new_relation") in ["at_war", "allied"]:
                try:
                    from backend.multiplayer.world_sync import (
                        sync_world_event_to_all,
                    )
                    await sync_world_event_to_all(
                        world_id=world_id,
                        event_title=(
                            f"Political Change: "
                            f"{change['faction_a']} and "
                            f"{change['faction_b']} are now "
                            f"{change['new_relation']}"
                        ),
                        event_description=(
                            f"The relationship between "
                            f"{change['faction_a']} and "
                            f"{change['faction_b']} has shifted "
                            f"to {change['new_relation']}."
                        ),
                        severity=(
                            "major" if change["new_relation"] == "at_war"
                            else "moderate"
                        ),
                    )
                except Exception as e:
                    logger.warning(f"Relation broadcast failed: {e}")

    except Exception as e:
        logger.error(f"Relation update failed: {e}")
        tick_result["errors"].append(f"relations: {e}")

    # Step 4: Economy update
    try:
        calculate_world_price_modifiers(world_id)
        tick_result["economy_updated"] = True
    except Exception as e:
        logger.error(f"Economy update failed: {e}")
        tick_result["errors"].append(f"economy: {e}")

    # Step 5: Narrative tick
    try:
        narrative_result = run_narrative_tick(world_id)
        tick_result["narrative_changes"] = narrative_result
    except Exception as e:
        logger.error(f"Narrative tick failed: {e}")
        tick_result["errors"].append(f"narrative: {e}")

    # Step 6: Log tick
    tick_result["duration_seconds"] = (
        datetime.utcnow() - tick_start
    ).total_seconds()

    log = _load_simulation_log()
    log.append(tick_result)
    _save_simulation_log(log)

    logger.info(
        f"Simulation tick complete | "
        f"world_id={world_id} | "
        f"factions={len(tick_result['faction_actions'])} | "
        f"errors={len(tick_result['errors'])} | "
        f"duration={tick_result['duration_seconds']:.2f}s"
    )

    return tick_result


def start_simulation(
    world_id: int,
    interval_minutes: int = 15,
):
    """
    Starts the autonomous simulation for a world.
    Runs every interval_minutes in the background.
    """
    job_id = f"simulation_world_{world_id}"

    if scheduler.get_job(job_id):
        logger.warning(
            f"Simulation already running for world {world_id}"
        )
        return False

    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")

    scheduler.add_job(
        run_simulation_tick,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id=job_id,
        args=[world_id],
        name=f"World {world_id} Simulation",
        replace_existing=True,
    )

    _active_world_ids.add(world_id)

    logger.info(
        f"Simulation started | "
        f"world_id={world_id} | "
        f"interval={interval_minutes}min"
    )
    return True


def stop_simulation(world_id: int):
    """Stops the simulation for a world."""
    job_id = f"simulation_world_{world_id}"
    job = scheduler.get_job(job_id)

    if job:
        scheduler.remove_job(job_id)
        _active_world_ids.discard(world_id)
        logger.info(f"Simulation stopped | world_id={world_id}")
        return True

    return False


def get_simulation_status() -> dict:
    """Returns current simulation status."""
    jobs = scheduler.get_jobs()
    return {
        "scheduler_running": scheduler.running,
        "active_worlds": list(_active_world_ids),
        "total_jobs": len(jobs),
        "jobs": [
            {
                "job_id": job.id,
                "name": job.name,
                "next_run": (
                    job.next_run_time.isoformat()
                    if job.next_run_time else None
                ),
            }
            for job in jobs
        ],
        "recent_ticks": _load_simulation_log()[-5:],
    }