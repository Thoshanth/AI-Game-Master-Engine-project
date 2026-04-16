import json
from collections import defaultdict
from backend.database.db import SessionLocal, PlayerAction, Player
from backend.database.world_store import get_player
from backend.logger import get_logger

logger = get_logger("prediction.sequence")

# Action sequence transition probabilities
# action_a → {action_b: probability}
# Built from observing thousands of player sessions
# These are our prior probabilities — updated by actual player data
TRANSITION_PRIORS = {
    "talked_to_npc": {
        "moved_to_location": 0.35,
        "talked_to_npc": 0.25,
        "completed_quest": 0.15,
        "collected_item": 0.10,
        "examined_object": 0.15,
    },
    "moved_to_location": {
        "talked_to_npc": 0.40,
        "examined_object": 0.25,
        "collected_item": 0.15,
        "fought_enemy": 0.10,
        "completed_quest": 0.10,
    },
    "fought_enemy": {
        "collected_item": 0.35,
        "fought_enemy": 0.25,
        "moved_to_location": 0.20,
        "completed_quest": 0.10,
        "talked_to_npc": 0.10,
    },
    "collected_item": {
        "moved_to_location": 0.30,
        "talked_to_npc": 0.25,
        "examined_object": 0.20,
        "fought_enemy": 0.15,
        "completed_quest": 0.10,
    },
    "completed_quest": {
        "talked_to_npc": 0.40,
        "moved_to_location": 0.30,
        "collected_item": 0.15,
        "examined_object": 0.15,
    },
    "examined_object": {
        "collected_item": 0.30,
        "talked_to_npc": 0.25,
        "moved_to_location": 0.25,
        "discovered_secret": 0.20,
    },
    "attacked_npc": {
        "fought_enemy": 0.40,
        "moved_to_location": 0.25,
        "collected_item": 0.20,
        "attacked_npc": 0.15,
    },
    "joined_faction": {
        "talked_to_npc": 0.45,
        "completed_quest": 0.25,
        "moved_to_location": 0.20,
        "collected_item": 0.10,
    },
    "discovered_secret": {
        "examined_object": 0.30,
        "talked_to_npc": 0.25,
        "moved_to_location": 0.25,
        "completed_quest": 0.20,
    },
    "player_helped": {
        "talked_to_npc": 0.35,
        "completed_quest": 0.30,
        "moved_to_location": 0.20,
        "collected_item": 0.15,
    },
}

# What content each predicted action needs pre-generated
CONTENT_NEEDS = {
    "moved_to_location": [
        "new_location_description",
        "npcs_at_destination",
        "available_quests",
    ],
    "talked_to_npc": [
        "npc_dialogue_context",
        "npc_current_mood",
        "relevant_rumors",
    ],
    "fought_enemy": [
        "enemy_stats",
        "combat_location_description",
        "loot_table",
    ],
    "discovered_secret": [
        "secret_description",
        "secret_lore",
        "quest_hook",
    ],
    "completed_quest": [
        "quest_completion_dialogue",
        "reward_description",
        "next_quest_hook",
    ],
}


def build_personal_transition_matrix(
    player_id: int,
    window: int = 50,
) -> dict:
    """
    Builds a personalized action transition matrix
    from the player's actual action history.

    Starts from the prior probabilities and updates
    them with the player's actual behavior patterns.
    The more a player plays, the more accurate this becomes.
    """
    db = SessionLocal()
    try:
        # Get recent actions
        recent_actions = db.query(PlayerAction).filter(
            PlayerAction.player_id == player_id
        ).order_by(
            PlayerAction.real_timestamp.desc()
        ).limit(window).all()

        if len(recent_actions) < 3:
            return TRANSITION_PRIORS.copy()

        # Reverse to chronological order
        recent_actions = list(reversed(recent_actions))

        # Count actual transitions
        transition_counts = defaultdict(lambda: defaultdict(int))
        for i in range(len(recent_actions) - 1):
            current = recent_actions[i].action_type
            next_action = recent_actions[i + 1].action_type
            transition_counts[current][next_action] += 1

        # Build personal matrix by blending prior + personal data
        personal_matrix = {}
        for action, transitions in TRANSITION_PRIORS.items():
            personal_counts = transition_counts.get(action, {})
            total_personal = sum(personal_counts.values())

            if total_personal == 0:
                # No personal data — use prior
                personal_matrix[action] = transitions.copy()
                continue

            # Blend: 40% prior + 60% personal data
            blended = {}
            all_next_actions = set(
                list(transitions.keys()) +
                list(personal_counts.keys())
            )

            for next_action in all_next_actions:
                prior_prob = transitions.get(next_action, 0.0)
                personal_prob = (
                    personal_counts.get(next_action, 0) /
                    total_personal
                )
                blended[next_action] = (
                    0.4 * prior_prob + 0.6 * personal_prob
                )

            # Normalize
            total = sum(blended.values())
            if total > 0:
                personal_matrix[action] = {
                    k: v / total
                    for k, v in blended.items()
                }
            else:
                personal_matrix[action] = transitions.copy()

        return personal_matrix

    finally:
        db.close()


def predict_next_actions(
    player_id: int,
    n_predictions: int = 3,
) -> dict:
    """
    Predicts the player's next N most likely actions.

    Returns predictions with confidence scores and
    what content should be pre-generated for each.
    """
    logger.info(
        f"Predicting next actions | "
        f"player_id={player_id}"
    )

    db = SessionLocal()
    try:
        # Get most recent action
        last_action = db.query(PlayerAction).filter(
            PlayerAction.player_id == player_id
        ).order_by(
            PlayerAction.real_timestamp.desc()
        ).first()

        player = db.query(Player).filter(
            Player.id == player_id
        ).first()

        if not player:
            return {"error": "Player not found"}

        if not last_action:
            return {
                "player_id": player_id,
                "last_action": None,
                "predictions": [],
                "message": "No actions yet — cannot predict",
            }

        last_action_type = last_action.action_type
        player_type = player.player_type or "unknown"

    finally:
        db.close()

    # Build personal transition matrix
    matrix = build_personal_transition_matrix(player_id)

    # Get transition probabilities from last action
    transitions = matrix.get(
        last_action_type,
        TRANSITION_PRIORS.get(last_action_type, {})
    )

    if not transitions:
        return {
            "player_id": player_id,
            "last_action": last_action_type,
            "predictions": [],
            "message": "No predictions available for this action",
        }

    # Sort by probability and take top N
    sorted_transitions = sorted(
        transitions.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:n_predictions]

    predictions = []
    for action, probability in sorted_transitions:
        content_needs = CONTENT_NEEDS.get(action, [])
        predictions.append({
            "predicted_action": action,
            "confidence": round(probability, 3),
            "confidence_label": _confidence_label(probability),
            "content_to_pre_generate": content_needs,
            "player_type_alignment": _check_type_alignment(
                action, player_type
            ),
        })

    logger.info(
        f"Predictions generated | "
        f"last={last_action_type} | "
        f"top={sorted_transitions[0][0]} ({sorted_transitions[0][1]:.2f})"
    )

    return {
        "player_id": player_id,
        "character_name": player.character_name if player else "Unknown",
        "last_action": last_action_type,
        "player_type": player_type,
        "predictions": predictions,
        "recommendation": (
            f"Pre-generate content for: "
            f"{sorted_transitions[0][0]}"
        ),
    }


def _confidence_label(prob: float) -> str:
    if prob >= 0.5:
        return "very_likely"
    elif prob >= 0.3:
        return "likely"
    elif prob >= 0.15:
        return "possible"
    else:
        return "unlikely"


def _check_type_alignment(
    action: str,
    player_type: str,
) -> str:
    """Checks if predicted action aligns with player type."""
    type_preferred_actions = {
        "explorer": [
            "moved_to_location", "examined_object",
            "discovered_secret", "talked_to_npc"
        ],
        "achiever": [
            "completed_quest", "collected_item",
            "fought_enemy", "leveled_up"
        ],
        "socializer": [
            "talked_to_npc", "joined_faction",
            "player_helped", "negotiated"
        ],
        "killer": [
            "attacked_npc", "fought_enemy",
            "threatened", "stole"
        ],
    }

    preferred = type_preferred_actions.get(player_type, [])
    if action in preferred:
        return "high_alignment"
    return "low_alignment"