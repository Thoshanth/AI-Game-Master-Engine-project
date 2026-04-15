import json
from backend.database.db import SessionLocal, Player, PlayerAction
from backend.database.world_store import get_player
from backend.logger import get_logger

logger = get_logger("narrative.profiler")

# Bartle player type definitions
PLAYER_TYPES = {
    "explorer": {
        "description": "Loves discovering new places, reading lore, understanding the world",
        "preferred_content": [
            "new locations", "hidden secrets", "world lore",
            "NPC backstories", "environmental storytelling"
        ],
        "action_indicators": [
            "moved_to_new_location", "read_lore", "talked_to_npc",
            "discovered_secret", "examined_object"
        ],
    },
    "achiever": {
        "description": "Completes quests, collects items, maximizes character power",
        "preferred_content": [
            "clear objectives", "rewards", "character progression",
            "rare items", "achievements"
        ],
        "action_indicators": [
            "completed_quest", "collected_item", "gained_experience",
            "leveled_up", "found_treasure"
        ],
    },
    "socializer": {
        "description": "Builds relationships, joins factions, talks to NPCs",
        "preferred_content": [
            "NPC relationships", "faction politics", "dialogue choices",
            "group activities", "reputation system"
        ],
        "action_indicators": [
            "talked_to_npc", "joined_faction", "helped_npc",
            "built_relationship", "negotiated"
        ],
    },
    "killer": {
        "description": "Engages in combat, chooses aggressive options, dominates",
        "preferred_content": [
            "combat encounters", "powerful weapons", "conquest",
            "defeating enemies", "territorial control"
        ],
        "action_indicators": [
            "attacked_npc", "fought_enemy", "threatened",
            "stole", "player_killed_npc"
        ],
    },
}


def analyze_player_behavior(player_id: int) -> dict:
    """
    Analyzes a player's action history to determine
    their Bartle player type and behavioral tendencies.

    Returns profile with type, confidence, and content preferences.
    """
    db = SessionLocal()
    try:
        player = db.query(Player).filter(
            Player.id == player_id
        ).first()
        if not player:
            return {}

        # Get all player actions
        actions = db.query(PlayerAction).filter(
            PlayerAction.player_id == player_id
        ).all()

        if not actions:
            return {
                "player_id": player_id,
                "player_type": "unknown",
                "confidence": 0.0,
                "message": "Not enough data — play more to get a profile",
            }

        # Count action types
        action_history = json.loads(player.action_history or "{}")
        total_actions = sum(action_history.values()) or 1

        # Score each player type
        type_scores = {}
        for player_type, config in PLAYER_TYPES.items():
            score = 0
            for indicator in config["action_indicators"]:
                count = action_history.get(indicator, 0)
                score += count

            type_scores[player_type] = score / total_actions

        # Determine primary type
        primary_type = max(type_scores, key=type_scores.get)
        primary_score = type_scores[primary_type]

        # Normalize scores
        total_score = sum(type_scores.values()) or 1
        type_percentages = {
            t: round(s / total_score * 100, 1)
            for t, s in type_scores.items()
        }

        # Confidence is high when one type dominates
        sorted_scores = sorted(type_scores.values(), reverse=True)
        confidence = (
            sorted_scores[0] - sorted_scores[1]
            if len(sorted_scores) > 1 else sorted_scores[0]
        )
        confidence = min(1.0, confidence * 5)

        # Generate content recommendations
        preferred_content = PLAYER_TYPES[primary_type]["preferred_content"]

        # Update player record
        player.player_type = primary_type
        player.player_type_confidence = confidence
        db.commit()

        profile = {
            "player_id": player_id,
            "character_name": player.character_name,
            "player_type": primary_type,
            "type_description": PLAYER_TYPES[primary_type]["description"],
            "confidence": round(confidence, 2),
            "type_breakdown": type_percentages,
            "total_actions_analyzed": len(actions),
            "preferred_content": preferred_content,
            "narrative_recommendations": _get_narrative_recommendations(
                primary_type, type_percentages
            ),
            "action_summary": {
                k: v for k, v in
                sorted(action_history.items(), key=lambda x: x[1], reverse=True)[:5]
            },
        }

        logger.info(
            f"Player profiled | player_id={player_id} | "
            f"type={primary_type} | confidence={confidence:.2f}"
        )

        return profile

    finally:
        db.close()


def _get_narrative_recommendations(
    primary_type: str,
    type_percentages: dict,
) -> list[str]:
    """
    Returns narrative content recommendations based on player type.
    Used by the narrative engine to customize world content.
    """
    recommendations = []

    if primary_type == "explorer":
        recommendations = [
            "Generate more hidden locations and secret passages",
            "Add more NPC backstories and world lore",
            "Create mysterious events that reward investigation",
            "Place rare books and historical records in dungeons",
        ]
    elif primary_type == "achiever":
        recommendations = [
            "Ensure clear quest objectives and visible progress",
            "Place rare items as dungeon rewards",
            "Create achievement milestones with tangible rewards",
            "Add skill-based challenges with powerful payoffs",
        ]
    elif primary_type == "socializer":
        recommendations = [
            "Generate NPCs with complex relationship webs",
            "Create faction political intrigue arcs",
            "Add dialogue choices with meaningful relationship impact",
            "Design quests that require NPC cooperation",
        ]
    elif primary_type == "killer":
        recommendations = [
            "Generate more combat encounters and dungeons",
            "Create rival players or faction enemies to defeat",
            "Add powerful weapons as quest rewards",
            "Design conquest opportunities with territory control",
        ]

    # Add hybrid recommendations if close split
    second_type = sorted(
        type_percentages.items(), key=lambda x: x[1], reverse=True
    )[1][0]

    if type_percentages.get(second_type, 0) > 30:
        recommendations.append(
            f"Strong {second_type} tendencies detected — "
            f"consider {PLAYER_TYPES[second_type]['preferred_content'][0]}"
        )

    return recommendations