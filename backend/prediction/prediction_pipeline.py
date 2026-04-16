import json
from backend.prediction.sequence_predictor import predict_next_actions
from backend.prediction.engagement_scorer import (
    calculate_session_engagement,
    score_content_by_response,
)
from backend.prediction.frustration_detector import detect_frustration
from backend.prediction.skill_assessor import assess_player_skill
from backend.narrative.player_profiler import analyze_player_behavior
from backend.procedural.location_generator import create_procedural_location
from backend.procedural.npc_generator import create_procedural_npc
from backend.database.world_store import (
    get_player, get_regions, get_locations,
)
from backend.logger import get_logger
import random

logger = get_logger("prediction.pipeline")


def full_player_prediction(
    player_id: int,
    world_id: int,
) -> dict:
    """
    Runs all prediction systems and returns a complete
    behavioral analysis with actionable recommendations.

    Used by the Game Master agent to adapt the world
    to this specific player.
    """
    logger.info(
        f"Full prediction | player_id={player_id} | "
        f"world_id={world_id}"
    )

    results = {
        "player_id": player_id,
        "world_id": world_id,
    }

    # Run all prediction systems
    try:
        results["next_actions"] = predict_next_actions(
            player_id, n_predictions=3
        )
    except Exception as e:
        logger.warning(f"Sequence prediction failed: {e}")
        results["next_actions"] = {}

    try:
        results["engagement"] = calculate_session_engagement(
            player_id, session_hours=24
        )
    except Exception as e:
        logger.warning(f"Engagement scoring failed: {e}")
        results["engagement"] = {}

    try:
        results["frustration"] = detect_frustration(
            player_id, window_minutes=30
        )
    except Exception as e:
        logger.warning(f"Frustration detection failed: {e}")
        results["frustration"] = {}

    try:
        results["skill"] = assess_player_skill(player_id)
    except Exception as e:
        logger.warning(f"Skill assessment failed: {e}")
        results["skill"] = {}

    try:
        results["behavior_profile"] = analyze_player_behavior(
            player_id
        )
    except Exception as e:
        logger.warning(f"Behavior profiling failed: {e}")
        results["behavior_profile"] = {}

    # Build unified recommendations
    results["unified_recommendations"] = (
        _build_unified_recommendations(results)
    )

    # Determine if pre-generation is needed
    results["pre_generation_needed"] = (
        _check_pre_generation_needed(results, world_id)
    )

    logger.info(
        f"Full prediction complete | "
        f"frustration={results.get('frustration', {}).get('frustration_level', 'unknown')} | "
        f"engagement={results.get('engagement', {}).get('engagement_label', 'unknown')} | "
        f"skill={results.get('skill', {}).get('overall_skill', 'unknown')}"
    )

    return results


def _build_unified_recommendations(results: dict) -> list[str]:
    """Combines recommendations from all prediction systems."""
    recs = []

    # From engagement
    engagement = results.get("engagement", {})
    if engagement.get("engagement_score", 5) < 4:
        recs.append(
            "LOW ENGAGEMENT: Spawn exciting nearby event immediately"
        )
    most_engaging = engagement.get("most_engaging_content")
    if most_engaging:
        recs.append(f"Generate more {most_engaging} content")

    # From frustration
    frustration = results.get("frustration", {})
    if frustration.get("requires_immediate_action"):
        recs.append(
            "HIGH FRUSTRATION: Immediate intervention required"
        )
    for intervention in frustration.get("interventions", [])[:2]:
        recs.append(intervention.get("suggestion", ""))

    # From skill
    skill = results.get("skill", {})
    diff_recs = skill.get("difficulty_recommendations", [])
    if diff_recs:
        recs.append(diff_recs[0])

    # From next action prediction
    next_actions = results.get("next_actions", {})
    predictions = next_actions.get("predictions", [])
    if predictions:
        top_pred = predictions[0]
        if top_pred.get("confidence", 0) > 0.4:
            content_needed = top_pred.get(
                "content_to_pre_generate", []
            )
            if content_needed:
                recs.append(
                    f"Pre-generate: {content_needed[0]} "
                    f"for predicted action: "
                    f"{top_pred['predicted_action']}"
                )

    return [r for r in recs if r]


def _check_pre_generation_needed(
    results: dict,
    world_id: int,
) -> dict:
    """
    Determines what content should be pre-generated
    based on predictions.
    """
    needed = {
        "location": False,
        "npc": False,
        "reason": "",
    }

    next_actions = results.get("next_actions", {})
    predictions = next_actions.get("predictions", [])

    if not predictions:
        return needed

    top = predictions[0]
    if (top.get("predicted_action") == "moved_to_location" and
            top.get("confidence", 0) > 0.4):
        needed["location"] = True
        needed["reason"] = (
            "Player likely to move to new location — "
            "pre-generating destination"
        )

    if (top.get("predicted_action") == "talked_to_npc" and
            top.get("confidence", 0) > 0.4):
        needed["npc"] = True
        needed["reason"] = (
            "Player likely to seek NPC — "
            "pre-generating NPC"
        )

    return needed


def pre_generate_predicted_content(
    player_id: int,
    world_id: int,
) -> dict:
    """
    Actually pre-generates content based on predictions.
    Called proactively to ensure zero wait time for player.
    """
    logger.info(
        f"Pre-generating content | "
        f"player_id={player_id}"
    )

    prediction = full_player_prediction(player_id, world_id)
    pre_gen = prediction.get("pre_generation_needed", {})
    generated = {}

    if pre_gen.get("location"):
        try:
            regions = get_regions(world_id)
            if regions:
                region = random.choice(regions)
                location = create_procedural_location(
                    world_id=world_id,
                    region_id=region.id,
                )
                generated["pre_generated_location"] = {
                    "id": location["id"],
                    "name": location["name"],
                    "type": location["type"],
                }
                logger.info(
                    f"Pre-generated location: "
                    f"{location['name']}"
                )
        except Exception as e:
            logger.warning(f"Location pre-gen failed: {e}")

    if pre_gen.get("npc"):
        try:
            regions = get_regions(world_id)
            if regions:
                locs = get_locations(regions[0].id)
                if locs:
                    npc = create_procedural_npc(
                        world_id=world_id,
                        location_id=locs[0].id,
                        role="quest_giver",
                    )
                    generated["pre_generated_npc"] = {
                        "id": npc["id"],
                        "name": npc["name"],
                        "role": npc["role"],
                    }
                    logger.info(
                        f"Pre-generated NPC: {npc['name']}"
                    )
        except Exception as e:
            logger.warning(f"NPC pre-gen failed: {e}")

    generated["prediction_basis"] = pre_gen.get("reason", "")
    return generated