import json
from datetime import datetime, timedelta
from backend.database.db import SessionLocal, PlayerAction, Player
from backend.logger import get_logger

logger = get_logger("prediction.skill")

SKILL_LEVELS = [
    (0.0, 0.2, "novice", "New player — needs guidance and simpler content"),
    (0.2, 0.4, "beginner", "Learning the systems — moderate challenge"),
    (0.4, 0.6, "intermediate", "Comfortable — ready for complex content"),
    (0.6, 0.8, "advanced", "Skilled — seeks challenging encounters"),
    (0.8, 1.0, "expert", "Mastery — needs hidden content and hard secrets"),
]


def assess_player_skill(player_id: int) -> dict:
    """
    Assesses player skill level across multiple dimensions.

    Dimensions:
    - Combat efficiency (damage taken per fight)
    - Quest completion rate (finished vs abandoned)
    - Discovery rate (secrets found per area visited)
    - Decision confidence (action speed)
    - Adaptation speed (how fast they learn new systems)
    """
    logger.info(f"Assessing skill | player_id={player_id}")

    db = SessionLocal()
    try:
        player = db.query(Player).filter(
            Player.id == player_id
        ).first()
        if not player:
            return {}

        all_actions = db.query(PlayerAction).filter(
            PlayerAction.player_id == player_id
        ).order_by(PlayerAction.real_timestamp.asc()).all()

        if not all_actions:
            return {
                "player_id": player_id,
                "overall_skill": "novice",
                "skill_score": 0.0,
                "message": "No actions yet — skill assessment unavailable",
            }

        action_history = json.loads(player.action_history or "{}")
        total_actions = sum(action_history.values()) or 1

        # Dimension 1: Quest completion rate
        quests_completed = action_history.get("completed_quest", 0)
        quests_started = action_history.get("accepted_quest", 1)
        quest_completion_rate = min(
            1.0, quests_completed / max(quests_started, 1)
        )

        # Dimension 2: Combat effectiveness
        fights = action_history.get("fought_enemy", 0)
        deaths = action_history.get("died", 0)
        if fights > 0:
            combat_score = max(0, 1.0 - (deaths / max(fights, 1)))
        else:
            combat_score = 0.5

        # Dimension 3: Discovery rate
        secrets_found = action_history.get("discovered_secret", 0)
        locations_visited = action_history.get("moved_to_location", 1)
        discovery_rate = min(
            1.0, secrets_found / max(locations_visited * 0.2, 1)
        )

        # Dimension 4: Action diversity
        unique_actions = len(action_history)
        diversity_score = min(1.0, unique_actions / 15)

        # Dimension 5: Decision speed
        if len(all_actions) >= 10:
            gaps = []
            for i in range(1, min(len(all_actions), 50)):
                gap = (
                    all_actions[i].real_timestamp -
                    all_actions[i-1].real_timestamp
                ).total_seconds()
                if gap < 300:
                    gaps.append(gap)

            if gaps:
                avg_gap = sum(gaps) / len(gaps)
                decision_speed = max(0, min(1.0, 1.0 - (avg_gap / 60)))
            else:
                decision_speed = 0.5
        else:
            decision_speed = 0.5

        # Calculate overall skill score
        overall_score = (
            quest_completion_rate * 0.25 +
            combat_score * 0.25 +
            discovery_rate * 0.20 +
            diversity_score * 0.15 +
            decision_speed * 0.15
        )

        # Determine skill level
        skill_level = "novice"
        skill_description = ""
        for min_s, max_s, level, desc in SKILL_LEVELS:
            if min_s <= overall_score < max_s:
                skill_level = level
                skill_description = desc
                break

        # Content difficulty recommendations
        difficulty_recommendations = _get_difficulty_recs(
            skill_level,
            combat_score,
            discovery_rate,
        )

        logger.info(
            f"Skill assessed | "
            f"player_id={player_id} | "
            f"level={skill_level} | "
            f"score={overall_score:.2f}"
        )

        return {
            "player_id": player_id,
            "character_name": player.character_name,
            "overall_skill": skill_level,
            "skill_score": round(overall_score, 3),
            "skill_description": skill_description,
            "dimensions": {
                "quest_completion_rate": round(
                    quest_completion_rate, 3
                ),
                "combat_effectiveness": round(combat_score, 3),
                "discovery_rate": round(discovery_rate, 3),
                "action_diversity": round(diversity_score, 3),
                "decision_speed": round(decision_speed, 3),
            },
            "raw_stats": {
                "total_actions": total_actions,
                "quests_completed": quests_completed,
                "secrets_found": secrets_found,
                "locations_visited": locations_visited,
                "combat_encounters": fights,
            },
            "difficulty_recommendations": difficulty_recommendations,
        }

    finally:
        db.close()


def _get_difficulty_recs(
    skill_level: str,
    combat_score: float,
    discovery_rate: float,
) -> list[str]:
    base_recs = {
        "novice": [
            "Use danger level 1-2 dungeons only",
            "Provide NPCs with clear quest directions",
            "Place obvious loot rewards for motivation",
        ],
        "beginner": [
            "Danger level 2-4 dungeons appropriate",
            "Mix clear and ambiguous quest objectives",
            "Include some hidden content discoverable with hints",
        ],
        "intermediate": [
            "Danger level 4-6 dungeons",
            "Multi-step quest chains with minimal hand-holding",
            "Hidden content discoverable by exploration",
        ],
        "advanced": [
            "Danger level 6-8 dungeons",
            "Complex multi-faction political quests",
            "Secrets requiring lateral thinking",
        ],
        "expert": [
            "Danger level 8-10 dungeons with unique mechanics",
            "Hidden quest chains requiring deep world knowledge",
            "Easter eggs only reachable through mastery",
        ],
    }.get(skill_level, [])

    extra_recs = []
    if combat_score < 0.4:
        extra_recs.append(
            "Combat difficulty should be reduced — "
            "player struggles in fights"
        )
    elif combat_score > 0.8:
        extra_recs.append(
            "Increase combat challenge — "
            "player dominates current encounters"
        )

    if discovery_rate > 0.5:
        extra_recs.append(
            "Player is an active explorer — "
            "hide more secrets and rewards"
        )

    return base_recs + extra_recs