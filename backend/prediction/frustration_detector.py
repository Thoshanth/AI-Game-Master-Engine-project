import json
from datetime import datetime, timedelta
from backend.database.db import SessionLocal, PlayerAction, Player
from backend.logger import get_logger

logger = get_logger("prediction.frustration")

# Frustration signal definitions
FRUSTRATION_SIGNALS = {
    "repeated_action": {
        "description": "Same action 3+ times in a row",
        "severity": "medium",
        "weight": 3,
    },
    "action_frequency_drop": {
        "description": "Actions per minute dropped by 50%+",
        "severity": "high",
        "weight": 4,
    },
    "aggressive_escalation": {
        "description": "Aggressive actions after neutral context",
        "severity": "medium",
        "weight": 3,
    },
    "quest_abandonment": {
        "description": "Started quest but stopped all quest actions",
        "severity": "high",
        "weight": 4,
    },
    "aimless_wandering": {
        "description": "Multiple location moves with no actions between",
        "severity": "low",
        "weight": 2,
    },
    "death_spiral": {
        "description": "Multiple failed combat attempts",
        "severity": "high",
        "weight": 5,
    },
}

# Intervention strategies for each frustration type
INTERVENTIONS = {
    "repeated_action": [
        "Spawn an NPC who notices the player struggling and offers help",
        "Trigger a world event that changes the situation",
        "Add a visible hint in the environment",
    ],
    "action_frequency_drop": [
        "Generate an exciting nearby event to re-engage",
        "Have a friendly NPC approach the player proactively",
        "Spawn a rare item visible in the distance",
    ],
    "aggressive_escalation": [
        "Provide an outlet — spawn a combat encounter",
        "Have an NPC acknowledge the player's frustration",
        "Create a quest that channels aggression productively",
    ],
    "quest_abandonment": [
        "Send the quest giver NPC to find the player",
        "Add a new hint to the quest journal",
        "Simplify next objective description",
    ],
    "aimless_wandering": [
        "Place an interesting NPC along their current path",
        "Trigger a nearby sound or visual cue",
        "Have a merchant appear with relevant items",
    ],
    "death_spiral": [
        "Spawn a healing potion nearby",
        "Reduce enemy spawn rate temporarily",
        "Have a companion NPC offer to help",
    ],
}

AGGRESSIVE_ACTIONS = {
    "attacked_npc", "stole", "threatened", "player_killed_npc"
}


def detect_frustration(
    player_id: int,
    window_minutes: int = 30,
) -> dict:
    """
    Analyzes recent player actions to detect frustration signals.

    Returns frustration level and recommended interventions.
    """
    logger.info(
        f"Detecting frustration | player_id={player_id}"
    )

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent_actions = db.query(PlayerAction).filter(
            PlayerAction.player_id == player_id,
            PlayerAction.real_timestamp >= cutoff,
        ).order_by(PlayerAction.real_timestamp.asc()).all()

        if len(recent_actions) < 2:
            return {
                "player_id": player_id,
                "frustration_level": "none",
                "frustration_score": 0,
                "signals": [],
                "message": "Not enough recent data",
            }

        detected_signals = []
        total_weight = 0

        # Signal 1: Repeated actions
        action_types = [a.action_type for a in recent_actions]
        if len(action_types) >= 3:
            for i in range(len(action_types) - 2):
                if (action_types[i] == action_types[i+1] ==
                        action_types[i+2]):
                    detected_signals.append({
                        "signal": "repeated_action",
                        **FRUSTRATION_SIGNALS["repeated_action"],
                        "detail": f"Repeated '{action_types[i]}' 3+ times",
                    })
                    total_weight += FRUSTRATION_SIGNALS[
                        "repeated_action"
                    ]["weight"]
                    break

        # Signal 2: Action frequency drop
        if len(recent_actions) >= 6:
            mid = len(recent_actions) // 2
            first_half = recent_actions[:mid]
            second_half = recent_actions[mid:]

            if len(first_half) >= 2 and len(second_half) >= 2:
                first_duration = max(
                    (first_half[-1].real_timestamp -
                     first_half[0].real_timestamp).total_seconds(),
                    1
                )
                second_duration = max(
                    (second_half[-1].real_timestamp -
                     second_half[0].real_timestamp).total_seconds(),
                    1
                )

                freq_first = len(first_half) / first_duration
                freq_second = len(second_half) / second_duration

                if freq_first > 0 and freq_second < freq_first * 0.5:
                    detected_signals.append({
                        "signal": "action_frequency_drop",
                        **FRUSTRATION_SIGNALS["action_frequency_drop"],
                        "detail": (
                            f"Frequency dropped from "
                            f"{freq_first:.2f} to {freq_second:.2f} "
                            f"actions/second"
                        ),
                    })
                    total_weight += FRUSTRATION_SIGNALS[
                        "action_frequency_drop"
                    ]["weight"]

        # Signal 3: Aggressive escalation
        neutral_then_aggressive = False
        for i in range(1, len(recent_actions)):
            if (recent_actions[i-1].action_type not in
                    AGGRESSIVE_ACTIONS and
                    recent_actions[i].action_type in
                    AGGRESSIVE_ACTIONS):
                neutral_then_aggressive = True
                break

        if neutral_then_aggressive:
            aggressive_count = sum(
                1 for a in recent_actions
                if a.action_type in AGGRESSIVE_ACTIONS
            )
            if aggressive_count >= 2:
                detected_signals.append({
                    "signal": "aggressive_escalation",
                    **FRUSTRATION_SIGNALS["aggressive_escalation"],
                    "detail": (
                        f"{aggressive_count} aggressive actions "
                        f"in window"
                    ),
                })
                total_weight += FRUSTRATION_SIGNALS[
                    "aggressive_escalation"
                ]["weight"]

        # Signal 4: Aimless wandering
        move_actions = [
            a for a in recent_actions
            if a.action_type == "moved_to_location"
        ]
        if len(move_actions) >= 3:
            # Check if moves have actions between them
            moves_without_actions = 0
            for i in range(1, len(recent_actions)):
                if (recent_actions[i].action_type == "moved_to_location"
                        and recent_actions[i-1].action_type ==
                        "moved_to_location"):
                    moves_without_actions += 1

            if moves_without_actions >= 2:
                detected_signals.append({
                    "signal": "aimless_wandering",
                    **FRUSTRATION_SIGNALS["aimless_wandering"],
                    "detail": (
                        f"{moves_without_actions} consecutive "
                        f"location moves"
                    ),
                })
                total_weight += FRUSTRATION_SIGNALS[
                    "aimless_wandering"
                ]["weight"]

        # Calculate frustration score and level
        frustration_score = min(10, total_weight)
        frustration_level = _frustration_level(frustration_score)

        # Get interventions for detected signals
        interventions = []
        for signal in detected_signals:
            signal_name = signal["signal"]
            signal_interventions = INTERVENTIONS.get(signal_name, [])
            if signal_interventions:
                interventions.append({
                    "for_signal": signal_name,
                    "suggestion": signal_interventions[0],
                    "alternatives": signal_interventions[1:],
                })

        logger.info(
            f"Frustration detected | "
            f"player_id={player_id} | "
            f"score={frustration_score} | "
            f"level={frustration_level} | "
            f"signals={len(detected_signals)}"
        )

        return {
            "player_id": player_id,
            "frustration_score": frustration_score,
            "frustration_level": frustration_level,
            "signals_detected": len(detected_signals),
            "signals": detected_signals,
            "interventions": interventions,
            "analysis_window_minutes": window_minutes,
            "actions_analyzed": len(recent_actions),
            "requires_immediate_action": frustration_score >= 7,
        }

    finally:
        db.close()


def _frustration_level(score: float) -> str:
    if score >= 8:
        return "critical"
    elif score >= 6:
        return "high"
    elif score >= 4:
        return "moderate"
    elif score >= 2:
        return "low"
    else:
        return "none"