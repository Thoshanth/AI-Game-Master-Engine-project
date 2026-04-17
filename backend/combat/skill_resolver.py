import json
from backend.combat.dice_engine import skill_check
from backend.combat.combat_narrator import narrate_skill_check
from backend.database.world_store import get_player, record_event
from backend.world_engine.world_clock import get_current_world_time
from backend.logger import get_logger

logger = get_logger("combat.skill")

# Skill types and which player stat they use
SKILL_STAT_MAP = {
    "pick_lock": "stealth",
    "sneak": "stealth",
    "hide": "stealth",
    "climb": "strength",
    "swim": "strength",
    "break_door": "strength",
    "lift_heavy": "strength",
    "recall_lore": "intelligence",
    "detect_trap": "intelligence",
    "read_ancient_text": "intelligence",
    "identify_herb": "intelligence",
    "persuade": "charisma",
    "intimidate": "charisma",
    "deceive": "charisma",
    "perform": "charisma",
    "track": "stealth",
    "forage": "intelligence",
    "first_aid": "intelligence",
    "craft": "intelligence",
}

# Difficulty classes for common scenarios
DIFFICULTY_CLASSES = {
    "trivial": 5,
    "easy": 8,
    "moderate": 12,
    "hard": 16,
    "very_hard": 20,
    "nearly_impossible": 25,
}


def resolve_skill_attempt(
    world_id: int,
    player_id: int,
    skill_type: str,
    difficulty: str = "moderate",
    context: str = "",
    location_id: int = None,
    advantage: bool = False,
    disadvantage: bool = False,
) -> dict:
    """
    Resolves a skill check for a player.

    Returns mechanical result + narrative description.
    Connects to world context for consistent narration.
    """
    logger.info(
        f"Skill check | player={player_id} | "
        f"skill={skill_type} | difficulty={difficulty}"
    )

    player = get_player(player_id)
    if not player:
        return {"error": "Player not found"}

    # Get relevant stat
    stat_name = SKILL_STAT_MAP.get(skill_type, "intelligence")
    stat_value = getattr(player, stat_name, 10)

    # Get difficulty class
    dc = DIFFICULTY_CLASSES.get(
        difficulty,
        DIFFICULTY_CLASSES["moderate"]
    )

    # Roll
    result = skill_check(
        skill_value=stat_value,
        difficulty=dc,
        advantage=advantage,
        disadvantage=disadvantage,
    )

    # Generate narrative
    narration = narrate_skill_check(
        player_name=player.character_name,
        skill_type=skill_type,
        degree=result["degree"],
        difficulty=difficulty,
        context=context,
    )

    # Determine reward/consequence
    reward = _calculate_skill_reward(
        skill_type, result["degree"]
    )

    # Record event if significant
    world_time = get_current_world_time(world_id)
    if result["degree"] in ["critical_success", "critical_failure"]:
        record_event(
            world_id=world_id,
            event_type="player_action",
            title=f"{player.character_name}: {skill_type.replace('_', ' ').title()}",
            description=narration,
            world_day=world_time.get("total_days", 0),
            location_id=location_id,
            player_id=player_id,
            importance=4,
        )

    return {
        "skill_type": skill_type,
        "stat_used": stat_name,
        "stat_value": stat_value,
        "difficulty": difficulty,
        "difficulty_class": dc,
        "roll": result["base_roll"],
        "total": result["total"],
        "degree": result["degree"],
        "success": result["success"],
        "margin": result["margin"],
        "narration": narration,
        "reward": reward,
        "advantage": advantage,
        "disadvantage": disadvantage,
    }


def _calculate_skill_reward(
    skill_type: str,
    degree: str,
) -> dict:
    """Determines what the player gains from a skill check."""
    rewards = {
        "critical_success": {
            "experience": 25,
            "bonus": "exceptional_outcome",
            "note": "Something extra happens beyond simple success",
        },
        "great_success": {
            "experience": 15,
            "bonus": None,
            "note": "Clean success with style",
        },
        "success": {
            "experience": 10,
            "bonus": None,
            "note": "Basic success",
        },
        "failure": {
            "experience": 5,
            "bonus": None,
            "note": "Failure — try again or different approach",
        },
        "critical_failure": {
            "experience": 5,
            "bonus": "negative_outcome",
            "note": "Something goes wrong beyond simple failure",
        },
    }
    return rewards.get(degree, {"experience": 0, "bonus": None})