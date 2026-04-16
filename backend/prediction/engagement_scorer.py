import json
from datetime import datetime, timedelta
from collections import defaultdict
from backend.database.db import SessionLocal, PlayerAction, Player
from backend.logger import get_logger

logger = get_logger("prediction.engagement")

# How many follow-up actions each content type generates
# Higher = more engaging
ENGAGEMENT_CONTENT_MAP = {
    "dungeon": [
        "fought_enemy", "collected_item", "discovered_secret",
        "examined_object",
    ],
    "npc_dialogue": [
        "talked_to_npc", "player_helped", "joined_faction",
        "completed_quest",
    ],
    "faction_quest": [
        "completed_quest", "joined_faction", "talked_to_npc",
    ],
    "exploration": [
        "moved_to_location", "examined_object",
        "discovered_secret",
    ],
    "combat": [
        "fought_enemy", "attacked_npc",
        "collected_item",
    ],
    "trading": [
        "traded", "collected_item", "talked_to_npc",
    ],
}


def calculate_session_engagement(
    player_id: int,
    session_hours: float = 24.0,
) -> dict:
    """
    Calculates engagement score for a player's recent session.

    Engagement = actions per hour + variety + streak length

    High engagement: many diverse actions in short time
    Low engagement: few actions, long gaps, repetition
    """
    logger.info(
        f"Calculating engagement | player_id={player_id}"
    )

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=session_hours)
        recent_actions = db.query(PlayerAction).filter(
            PlayerAction.player_id == player_id,
            PlayerAction.real_timestamp >= cutoff,
        ).order_by(PlayerAction.real_timestamp.asc()).all()

        if not recent_actions:
            return {
                "player_id": player_id,
                "engagement_score": 0.0,
                "engagement_label": "no_recent_activity",
                "actions_in_period": 0,
            }

        total_actions = len(recent_actions)

        # Actions per hour
        if total_actions > 1:
            time_span = (
                recent_actions[-1].real_timestamp -
                recent_actions[0].real_timestamp
            ).total_seconds() / 3600
            actions_per_hour = (
                total_actions / max(time_span, 0.1)
            )
        else:
            actions_per_hour = 1.0

        # Action variety (unique action types / total)
        action_types = [a.action_type for a in recent_actions]
        unique_types = len(set(action_types))
        variety_score = unique_types / max(total_actions, 1)

        # Streak detection (consecutive actions without long gaps)
        max_streak = 0
        current_streak = 1
        for i in range(1, len(recent_actions)):
            gap = (
                recent_actions[i].real_timestamp -
                recent_actions[i-1].real_timestamp
            ).total_seconds()
            if gap < 300:  # less than 5 min gap
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1

        # Content type breakdown
        content_engagement = {}
        for content_type, indicators in ENGAGEMENT_CONTENT_MAP.items():
            count = sum(
                1 for a in recent_actions
                if a.action_type in indicators
            )
            content_engagement[content_type] = count

        # Most engaging content
        most_engaging = max(
            content_engagement.items(),
            key=lambda x: x[1]
        ) if content_engagement else ("none", 0)

        # Calculate overall score (0-10)
        aph_score = min(10, actions_per_hour * 2)
        variety_scaled = variety_score * 10
        streak_score = min(10, max_streak / 3)

        engagement_score = (
            aph_score * 0.4 +
            variety_scaled * 0.3 +
            streak_score * 0.3
        )

        engagement_label = _engagement_label(engagement_score)

        logger.info(
            f"Engagement calculated | "
            f"player_id={player_id} | "
            f"score={engagement_score:.1f} | "
            f"label={engagement_label}"
        )

        return {
            "player_id": player_id,
            "engagement_score": round(engagement_score, 2),
            "engagement_label": engagement_label,
            "actions_in_period": total_actions,
            "actions_per_hour": round(actions_per_hour, 1),
            "action_variety": round(variety_score, 2),
            "max_action_streak": max_streak,
            "content_engagement": content_engagement,
            "most_engaging_content": most_engaging[0],
            "analysis_period_hours": session_hours,
            "recommendations": _engagement_recommendations(
                engagement_score,
                most_engaging[0],
                content_engagement,
            ),
        }

    finally:
        db.close()


def score_content_by_response(
    player_id: int,
    content_type: str,
    window_actions: int = 10,
) -> float:
    """
    Scores how engaging a specific content type is
    for this player by looking at follow-up actions.

    If player does many actions after a dungeon → dungeon engaging.
    If player goes offline after a city → city not engaging.
    """
    db = SessionLocal()
    try:
        all_actions = db.query(PlayerAction).filter(
            PlayerAction.player_id == player_id
        ).order_by(
            PlayerAction.real_timestamp.asc()
        ).all()

        if len(all_actions) < window_actions:
            return 5.0  # Default neutral score

        indicators = ENGAGEMENT_CONTENT_MAP.get(content_type, [])
        if not indicators:
            return 5.0

        # Find occurrences of content type and measure follow-up activity
        scores = []
        for i, action in enumerate(all_actions):
            if action.action_type in indicators:
                # Look at next N actions
                window_end = min(i + window_actions, len(all_actions))
                follow_ups = all_actions[i+1:window_end]

                if not follow_ups:
                    continue

                # Score = diversity of follow-up actions
                follow_up_types = set(
                    a.action_type for a in follow_ups
                )
                score = len(follow_up_types) / window_actions * 10
                scores.append(score)

        return round(sum(scores) / len(scores), 2) if scores else 5.0

    finally:
        db.close()


def _engagement_label(score: float) -> str:
    if score >= 8:
        return "highly_engaged"
    elif score >= 6:
        return "engaged"
    elif score >= 4:
        return "moderately_engaged"
    elif score >= 2:
        return "low_engagement"
    else:
        return "disengaged"


def _engagement_recommendations(
    score: float,
    most_engaging: str,
    content_map: dict,
) -> list[str]:
    recs = []

    if score < 4:
        recs.append(
            "Player showing low engagement — spawn an exciting event nearby"
        )
        recs.append(
            "Consider sending an NPC with an urgent quest to re-engage"
        )

    if most_engaging and most_engaging != "none":
        recs.append(
            f"Player most engaged by {most_engaging} — "
            f"generate more {most_engaging} content"
        )

    # Find least engaging content
    if content_map:
        least = min(content_map.items(), key=lambda x: x[1])
        if least[1] == 0:
            recs.append(
                f"Player avoids {least[0]} — "
                f"either redesign or remove from their path"
            )

    return recs