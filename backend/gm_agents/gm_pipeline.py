import json
from pathlib import Path
from datetime import datetime
from backend.gm_agents.gm_state import create_initial_gm_state
from backend.gm_agents.gm_graph import gm_graph
from backend.database.world_store import (
    get_all_worlds, get_player, get_recent_events,
)
from backend.prediction.prediction_pipeline import full_player_prediction
from backend.logger import get_logger

logger = get_logger("gm_agents.pipeline")

GM_LOG_PATH = Path("game_data/gm_log.json")


def run_gm_system(
    world_id: int,
    player_id: int,
    trigger: str,
    trigger_data: dict = None,
    show_agent_trace: bool = False,
) -> dict:
    """
    Runs the complete 5-agent Game Master system.

    Triggers:
    player_entered_location  → describe scene
    player_completed_quest   → reward + next hook
    player_action_major      → consequence narration
    player_idle_too_long     → inject engagement
    player_low_engagement    → inject excitement
    player_high_frustration  → inject helper
    npc_wants_to_speak       → proactive NPC
    world_event_major        → update world narrative

    Returns the GM's complete response with
    scene description, NPC actions, content hooks.
    """
    logger.info(
        f"GM System | world={world_id} | "
        f"player={player_id} | trigger={trigger}"
    )

    initial_state = create_initial_gm_state(
        world_id=world_id,
        player_id=player_id,
        trigger=trigger,
        trigger_data=trigger_data or {},
    )

    # Run the LangGraph workflow
    logger.info("Invoking GM LangGraph")
    final_state = gm_graph.invoke(initial_state)

    # Build response
    response = {
        "world_id": world_id,
        "player_id": player_id,
        "trigger": trigger,
        "generated_at": datetime.utcnow().isoformat(),
        "final_response": final_state.get("final_response", ""),
        "scene_description": final_state.get("scene_description", ""),
        "suggested_actions": final_state.get("suggested_actions", []),
        "proactive_npcs": final_state.get("proactive_npcs", [])[:3],
        "immediate_events": final_state.get("immediate_events", []),
        "upcoming_hooks": final_state.get("upcoming_hooks", []),
        "conflict_detected": final_state.get("conflict_detected", False),
        "conflict_resolution": final_state.get("conflict_resolution", {}),
        "continuity_approved": final_state.get("continuity_approved", False),
        "continuity_issues": final_state.get("continuity_issues", []),
        "iterations_used": final_state.get("iterations", 0),
        "content_plan": final_state.get("content_plan", {}),
    }

    if show_agent_trace:
        response["agent_trace"] = final_state.get("agent_log", [])

    # Log GM response
    _log_gm_response(response)

    logger.info(
        f"GM System complete | "
        f"trigger={trigger} | "
        f"approved={response['continuity_approved']} | "
        f"iterations={response['iterations_used']}"
    )

    return response


def run_proactive_gm_tick(world_id: int) -> list[dict]:
    """
    Proactive GM tick — checks all online players
    and generates GM responses for those who need attention.

    Called by the simulation scheduler alongside
    the economy/faction tick.
    """
    from backend.multiplayer.connection_manager import manager
    from backend.multiplayer.world_sync import sync_world_event_to_all

    logger.info(f"Proactive GM tick | world={world_id}")

    online_players = manager.get_online_players(world_id)
    responses = []

    for player_info in online_players:
        player_id = player_info["player_id"]

        try:
            # Check player state
            prediction = full_player_prediction(
                player_id, world_id
            )

            frustration = prediction.get(
                "frustration", {}
            ).get("frustration_level", "none")

            engagement = prediction.get(
                "engagement", {}
            ).get("engagement_score", 5)

            trigger = None
            if frustration in ["high", "critical"]:
                trigger = "player_high_frustration"
            elif engagement < 3:
                trigger = "player_low_engagement"

            if trigger:
                gm_response = run_gm_system(
                    world_id=world_id,
                    player_id=player_id,
                    trigger=trigger,
                    trigger_data={
                        "location_id": player_info.get(
                            "current_location"
                        ),
                    },
                )
                responses.append({
                    "player_id": player_id,
                    "trigger": trigger,
                    "response": gm_response.get(
                        "final_response", ""
                    )[:200],
                })

        except Exception as e:
            logger.warning(
                f"Proactive GM failed for player "
                f"{player_id}: {e}"
            )

    logger.info(
        f"Proactive GM tick complete | "
        f"players_checked={len(online_players)} | "
        f"responses={len(responses)}"
    )
    return responses


def _log_gm_response(response: dict):
    """Logs GM response for debugging and review."""
    try:
        log = []
        if GM_LOG_PATH.exists():
            with open(GM_LOG_PATH) as f:
                log = json.load(f)

        log.append({
            "timestamp": response["generated_at"],
            "trigger": response["trigger"],
            "player_id": response["player_id"],
            "world_id": response["world_id"],
            "approved": response["continuity_approved"],
            "iterations": response["iterations_used"],
            "response_preview": response[
                "final_response"
            ][:100],
        })

        GM_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GM_LOG_PATH, "w") as f:
            json.dump(log[-50:], f, indent=2)

    except Exception as e:
        logger.warning(f"GM log failed: {e}")