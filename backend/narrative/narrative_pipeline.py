import json
from backend.narrative.consequence_engine import generate_consequences
from backend.narrative.arc_generator import (
    generate_story_arc, get_active_arcs,
    advance_arc_stage, resolve_arc, get_all_arcs,
)
from backend.narrative.plot_tracker import (
    get_world_narrative_state, create_thread,
    get_all_threads,
)
from backend.narrative.player_profiler import analyze_player_behavior
from backend.database.world_store import (
    get_recent_events, record_player_action,
    get_world_summary,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.npc_memory.emotion_engine import decay_emotions
from backend.procedural.event_generator import run_autonomous_world_tick
from backend.logger import get_logger

logger = get_logger("narrative.pipeline")


def process_player_action(
    world_id: int,
    player_id: int,
    action_type: str,
    action_description: str,
    location_id: int = None,
    target_npc_id: int = None,
    target_faction_id: int = None,
    generate_arc: bool = False,
) -> dict:
    """
    Master function for processing any significant player action.

    Runs the full narrative pipeline:
    1. Record action in database
    2. Generate consequences
    3. Update player behavior profile
    4. Optionally generate new story arc
    5. Create plot thread
    6. Return full narrative response

    This is called whenever a player does something meaningful.
    """
    logger.info(
        f"Processing player action | "
        f"type={action_type} | player={player_id}"
    )

    world_time = get_current_world_time(world_id)

    # Step 1: Record action
    record_player_action(
        player_id=player_id,
        world_id=world_id,
        action_type=action_type,
        action_detail=action_description,
        location_id=location_id,
        target_npc_id=target_npc_id,
        world_day=world_time.get("total_days", 0.0),
        outcome=action_description,
    )

    # Step 2: Generate consequences
    consequences = {}
    try:
        consequences = generate_consequences(
            world_id=world_id,
            action_type=action_type,
            player_id=player_id,
            target_npc_id=target_npc_id,
            target_faction_id=target_faction_id,
            location_id=location_id,
            action_description=action_description,
        )
    except Exception as e:
        logger.warning(f"Consequence generation failed: {e}")

    # Step 3: Update player profile
    player_profile = {}
    try:
        player_profile = analyze_player_behavior(player_id)
    except Exception as e:
        logger.warning(f"Player profiling failed: {e}")

    # Step 4: Generate story arc if action is major
    new_arc = None
    severity = consequences.get("severity", "minor")
    should_generate_arc = (
        generate_arc or
        severity in ["major", "catastrophic"]
    )

    if should_generate_arc:
        try:
            active_arcs = get_active_arcs(world_id)
            # Don't generate arc if already have 3+ active
            if len(active_arcs) < 3:
                new_arc = generate_story_arc(
                    world_id=world_id,
                    trigger_event=action_description,
                    player_id=player_id,
                )
        except Exception as e:
            logger.warning(f"Arc generation failed: {e}")

    # Step 5: Create plot thread
    new_thread = None
    try:
        new_thread = create_thread(
            world_id=world_id,
            title=consequences.get(
                "action_summary",
                f"Consequence of {action_type}"
            ),
            description=action_description,
            thread_type=action_type,
            player_id=player_id,
            arc_id=new_arc.get("arc_id") if new_arc else None,
            urgency=(
                "high" if severity in ["major", "catastrophic"]
                else "medium" if severity == "moderate"
                else "low"
            ),
        )
    except Exception as e:
        logger.warning(f"Thread creation failed: {e}")

    return {
        "action_processed": True,
        "action_type": action_type,
        "severity": severity,
        "consequences": consequences,
        "player_type": player_profile.get("player_type", "unknown"),
        "new_arc_generated": new_arc is not None,
        "new_arc": {
            "arc_id": new_arc.get("arc_id"),
            "title": new_arc.get("title"),
            "logline": new_arc.get("logline"),
        } if new_arc else None,
        "plot_thread_created": new_thread is not None,
        "quest_opportunities": consequences.get("quest_opportunities", []),
        "rumors_generated": consequences.get("rumors_generated", []),
        "world_day": world_time.get("total_days", 0.0),
    }


def run_narrative_tick(world_id: int) -> dict:
    """
    Advances the narrative state of the world.
    Called automatically by the world tick scheduler.

    Does:
    1. Advances story arc stages if time has passed
    2. Decays NPC emotions
    3. Runs autonomous world events
    4. Checks for arc resolutions

    Returns summary of narrative changes.
    """
    logger.info(f"Narrative tick | world_id={world_id}")

    world_time = get_current_world_time(world_id)
    current_day = world_time.get("total_days", 0.0)

    changes = {
        "arcs_advanced": [],
        "world_events": [],
        "emotions_decayed": True,
    }

    # Advance arc stages based on time
    active_arcs = get_active_arcs(world_id)
    for arc in active_arcs:
        created_day = arc.get("created_day", 0)
        days_active = current_day - created_day
        duration = arc.get("estimated_duration_days", 14)

        current_stage = arc.get("stage", "setup")

        if days_active > duration * 0.7 and current_stage == "rising":
            advanced = advance_arc_stage(arc["arc_id"], "climax")
            changes["arcs_advanced"].append({
                "arc_id": arc["arc_id"],
                "title": arc.get("title"),
                "new_stage": "climax",
            })
        elif days_active > duration * 0.3 and current_stage == "setup":
            advanced = advance_arc_stage(arc["arc_id"], "rising")
            changes["arcs_advanced"].append({
                "arc_id": arc["arc_id"],
                "title": arc.get("title"),
                "new_stage": "rising",
            })
        elif days_active > duration and current_stage == "climax":
            # Auto-resolve with "player ignored" ending
            resolved = resolve_arc(arc["arc_id"], "resolution_c")
            changes["arcs_advanced"].append({
                "arc_id": arc["arc_id"],
                "title": arc.get("title"),
                "new_stage": "resolved",
                "auto_resolved": True,
            })

    # Decay emotions
    decay_emotions(world_id, days_passed=0.5)

    # Run autonomous world events
    try:
        world_events = run_autonomous_world_tick(world_id)
        changes["world_events"] = [
            e.get("title", "Unknown event")
            for e in world_events[:3]
        ]
    except Exception as e:
        logger.warning(f"World tick failed: {e}")

    logger.info(
        f"Narrative tick complete | "
        f"arcs_advanced={len(changes['arcs_advanced'])} | "
        f"world_events={len(changes['world_events'])}"
    )

    return changes