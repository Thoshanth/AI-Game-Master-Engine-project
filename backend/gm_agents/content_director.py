import json
import random
from backend.prediction.prediction_pipeline import full_player_prediction
from backend.narrative.arc_generator import get_active_arcs
from backend.narrative.plot_tracker import get_world_narrative_state
from backend.simulation.economy_engine import get_current_prices
from backend.database.world_store import (
    get_available_quests, get_regions,
)
from backend.logger import get_logger

logger = get_logger("gm_agents.content_director")


def content_director_agent(state: dict) -> dict:
    """
    Agent 2 — Content Director

    Plans what content should appear next based on:
    - Player behavior prediction (Stage 5)
    - Active narrative arcs (Stage 4)
    - World economic state (Stage 7)
    - Player engagement score

    Ensures the right content at the right time —
    no more random dungeons appearing for socializer players.

    Reads:  world_id, player_id, scene_description
    Writes: content_plan, immediate_events, upcoming_hooks
    """
    world_id = state["world_id"]
    player_id = state["player_id"]
    trigger = state["trigger"]
    iteration = state.get("iterations", 0)

    logger.info(
        f"Content Director | world={world_id} | "
        f"player={player_id} | iter={iteration}"
    )

    # Get player prediction
    prediction = {}
    try:
        prediction = full_player_prediction(player_id, world_id)
    except Exception as e:
        logger.warning(f"Prediction failed in content director: {e}")

    player_type = prediction.get(
        "behavior_profile", {}
    ).get("player_type", "unknown")

    engagement_score = prediction.get(
        "engagement", {}
    ).get("engagement_score", 5)

    frustration_level = prediction.get(
        "frustration", {}
    ).get("frustration_level", "none")

    next_actions = prediction.get(
        "next_actions", {}
    ).get("predictions", [])

    top_predicted = (
        next_actions[0]["predicted_action"]
        if next_actions else "explore"
    )

    # Get active arcs
    active_arcs = []
    try:
        active_arcs = get_active_arcs(world_id)
    except Exception as e:
        logger.warning(f"Arc fetch failed: {e}")

    # Get available quests
    quests = []
    try:
        quests = get_available_quests(world_id)
    except Exception as e:
        logger.warning(f"Quest fetch failed: {e}")

    # Build content plan based on player type
    immediate_events = []
    upcoming_hooks = []
    recommended_type = "general"

    if frustration_level in ["high", "critical"]:
        immediate_events.append({
            "type": "rescue_hook",
            "description": (
                "Spawn a distressed NPC nearby with an urgent, "
                "easy-to-understand task"
            ),
            "priority": "immediate",
            "reason": "Player frustration detected",
        })

    if engagement_score < 4:
        immediate_events.append({
            "type": "world_event",
            "description": (
                "Trigger an exciting nearby event — "
                "combat sounds, mysterious figure, "
                "or faction confrontation"
            ),
            "priority": "high",
            "reason": "Low engagement detected",
        })

    # Player type specific content
    type_content = {
        "explorer": {
            "recommended_type": "discovery",
            "events": [
                "hidden passage hint in scene",
                "mysterious note found",
                "NPC mentions unexplored location",
            ],
        },
        "achiever": {
            "recommended_type": "quest",
            "events": [
                "quest update notification",
                "rare item spotted",
                "skill challenge opportunity",
            ],
        },
        "socializer": {
            "recommended_type": "social",
            "events": [
                "NPC with interesting backstory approaches",
                "faction political drama nearby",
                "rumor about player's reputation spreads",
            ],
        },
        "killer": {
            "recommended_type": "combat",
            "events": [
                "enemy patrol visible",
                "bounty board updated",
                "faction soldier provocation",
            ],
        },
    }

    type_config = type_content.get(player_type, {
        "recommended_type": "general",
        "events": ["interesting NPC nearby", "world event"],
    })

    recommended_type = type_config["recommended_type"]
    upcoming_hooks = type_config["events"][:2]

    # Add arc hooks if active arcs exist
    if active_arcs:
        arc = active_arcs[0]
        upcoming_hooks.append(
            f"Arc hint: {arc.get('logline', 'Something stirs in the world')}"
        )

    # Add quest hook if quests available
    if quests:
        quest = quests[0]
        upcoming_hooks.append(
            f"Quest available: {quest.title}"
        )

    content_plan = {
        "player_type": player_type,
        "engagement_score": engagement_score,
        "frustration_level": frustration_level,
        "top_predicted_action": top_predicted,
        "recommended_content_type": recommended_type,
        "active_arcs": len(active_arcs),
        "available_quests": len(quests),
    }

    logger.info(
        f"Content Director complete | "
        f"type={player_type} | "
        f"engagement={engagement_score} | "
        f"frustration={frustration_level} | "
        f"events={len(immediate_events)}"
    )

    return {
        "content_plan": content_plan,
        "immediate_events": immediate_events,
        "upcoming_hooks": upcoming_hooks,
        "recommended_content_type": recommended_type,
        "agent_log": state.get("agent_log", []) + [{
            "agent": "ContentDirector",
            "iteration": iteration,
            "player_type": player_type,
            "engagement": engagement_score,
            "frustration": frustration_level,
            "events_planned": len(immediate_events),
        }],
    }