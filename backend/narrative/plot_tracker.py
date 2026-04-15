import json
from pathlib import Path
from datetime import datetime
from backend.database.world_store import get_recent_events, get_world_summary
from backend.world_engine.world_clock import get_current_world_time
from backend.narrative.arc_generator import get_active_arcs, get_all_arcs
from backend.logger import get_logger

logger = get_logger("narrative.plot_tracker")

PLOT_STORAGE = Path("game_data/plot_threads")
PLOT_STORAGE.mkdir(parents=True, exist_ok=True)


def get_all_threads(world_id: int) -> list[dict]:
    """Returns all plot threads for a world."""
    threads = []
    for f in PLOT_STORAGE.glob(f"thread_{world_id}_*.json"):
        with open(f) as fp:
            threads.append(json.load(fp))
    return sorted(threads, key=lambda t: t.get("created_day", 0))


def create_thread(
    world_id: int,
    title: str,
    description: str,
    thread_type: str,
    player_id: int = None,
    arc_id: str = None,
    urgency: str = "low",
) -> dict:
    """Creates a new plot thread."""
    world_time = get_current_world_time(world_id)
    thread_id = f"thread_{world_id}_{datetime.utcnow().timestamp():.0f}"

    thread = {
        "thread_id": thread_id,
        "world_id": world_id,
        "title": title,
        "description": description,
        "thread_type": thread_type,
        "player_id": player_id,
        "arc_id": arc_id,
        "urgency": urgency,
        "status": "active",
        "created_day": world_time.get("total_days", 0.0),
        "events": [],
        "connections": [],
    }

    thread_path = PLOT_STORAGE / f"{thread_id}.json"
    with open(thread_path, "w") as f:
        json.dump(thread, f, indent=2)

    logger.info(f"Plot thread created | id={thread_id} | title='{title}'")
    return thread


def add_event_to_thread(thread_id: str, event: dict):
    """Adds an event to a plot thread's history."""
    thread_path = PLOT_STORAGE / f"{thread_id}.json"
    if not thread_path.exists():
        return

    with open(thread_path) as f:
        thread = json.load(f)

    thread["events"].append({
        "description": event.get("description", ""),
        "world_day": event.get("world_day", 0),
        "event_type": event.get("type", "unknown"),
    })

    with open(thread_path, "w") as f:
        json.dump(thread, f, indent=2)


def connect_threads(thread_id_a: str, thread_id_b: str, connection: str):
    """
    Records that two plot threads are connected.
    Used to track when storylines intersect.
    """
    for thread_id in [thread_id_a, thread_id_b]:
        thread_path = PLOT_STORAGE / f"{thread_id}.json"
        if not thread_path.exists():
            continue

        with open(thread_path) as f:
            thread = json.load(f)

        other_id = (
            thread_id_b if thread_id == thread_id_a else thread_id_a
        )
        thread["connections"].append({
            "connected_thread": other_id,
            "connection_description": connection,
        })

        with open(thread_path, "w") as f:
            json.dump(thread, f, indent=2)


def resolve_thread(thread_id: str, resolution: str):
    """Marks a plot thread as resolved."""
    thread_path = PLOT_STORAGE / f"{thread_id}.json"
    if not thread_path.exists():
        return

    with open(thread_path) as f:
        thread = json.load(f)

    thread["status"] = "resolved"
    thread["resolution"] = resolution

    with open(thread_path, "w") as f:
        json.dump(thread, f, indent=2)

    logger.info(f"Thread resolved | id={thread_id}")


def get_world_narrative_state(world_id: int) -> dict:
    """
    Returns the complete narrative state of the world.
    Shows all active arcs, threads, and tensions.
    Used to give GMs (and LLM) full story context.
    """
    all_threads = get_all_threads(world_id)
    active_threads = [
        t for t in all_threads if t.get("status") == "active"
    ]
    resolved_threads = [
        t for t in all_threads if t.get("status") == "resolved"
    ]

    all_arcs = get_all_arcs(world_id)
    active_arcs = get_active_arcs(world_id)
    resolved_arcs = [
        a for a in all_arcs if a.get("status") == "resolved"
    ]

    recent_events = get_recent_events(
        world_id, limit=10, notable_only=True
    )

    world_time = get_current_world_time(world_id)

    # Find thread connections
    connections = []
    for thread in active_threads:
        for conn in thread.get("connections", []):
            connections.append({
                "thread_a": thread["title"],
                "thread_b": conn["connected_thread"],
                "connection": conn["connection_description"],
            })

    # Urgency summary
    urgency_count = {
        "critical": sum(
            1 for t in active_threads if t.get("urgency") == "critical"
        ),
        "high": sum(
            1 for t in active_threads if t.get("urgency") == "high"
        ),
        "medium": sum(
            1 for t in active_threads if t.get("urgency") == "medium"
        ),
        "low": sum(
            1 for t in active_threads if t.get("urgency") == "low"
        ),
    }

    return {
        "world_id": world_id,
        "current_time": world_time.get("time_string", "Unknown"),
        "narrative_summary": {
            "active_arcs": len(active_arcs),
            "resolved_arcs": len(resolved_arcs),
            "active_threads": len(active_threads),
            "resolved_threads": len(resolved_threads),
            "thread_connections": len(connections),
        },
        "urgency_breakdown": urgency_count,
        "active_arcs": [
            {
                "arc_id": a.get("arc_id"),
                "title": a.get("title"),
                "type": a.get("type"),
                "stage": a.get("stage"),
                "logline": a.get("logline"),
                "urgency": a.get("urgency"),
                "created_day": a.get("created_day"),
            }
            for a in active_arcs
        ],
        "active_threads": [
            {
                "thread_id": t.get("thread_id"),
                "title": t.get("title"),
                "type": t.get("thread_type"),
                "urgency": t.get("urgency"),
                "event_count": len(t.get("events", [])),
            }
            for t in active_threads
        ],
        "thread_connections": connections,
        "recent_notable_events": [
            {
                "title": e.title,
                "description": e.description[:100],
                "world_day": e.world_day,
            }
            for e in recent_events
        ],
    }