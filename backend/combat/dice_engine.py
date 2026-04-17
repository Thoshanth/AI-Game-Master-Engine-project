import random
import math
from backend.logger import get_logger

logger = get_logger("combat.dice")


def roll(sides: int, count: int = 1, modifier: int = 0) -> dict:
    """
    Rolls count dice with given sides and adds modifier.

    roll(20) → standard d20 check
    roll(6, 2) → 2d6 damage
    roll(6, 2, 3) → 2d6+3 damage
    """
    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier

    result = {
        "dice": f"{count}d{sides}+{modifier}" if modifier else f"{count}d{sides}",
        "rolls": rolls,
        "modifier": modifier,
        "total": total,
        "is_critical_success": sides == 20 and rolls[0] == 20,
        "is_critical_failure": sides == 20 and rolls[0] == 1,
    }

    logger.debug(
        f"Dice roll | {result['dice']} | "
        f"rolls={rolls} | total={total}"
    )
    return result


def roll_initiative(
    player_stats: dict,
    enemy_stats: dict,
) -> dict:
    """
    Rolls initiative for both sides.
    Higher roll acts first.
    Ties broken by dexterity/stealth stat.
    """
    player_roll = roll(20, modifier=player_stats.get("stealth", 10) // 3)
    enemy_roll = roll(20, modifier=enemy_stats.get("agility", 10) // 3)

    player_wins = player_roll["total"] >= enemy_roll["total"]

    return {
        "player_roll": player_roll["total"],
        "enemy_roll": enemy_roll["total"],
        "player_goes_first": player_wins,
        "initiative_margin": abs(
            player_roll["total"] - enemy_roll["total"]
        ),
    }


def calculate_hit_chance(
    attacker_skill: int,
    defender_defense: int,
    difficulty_class: int = 10,
) -> dict:
    """
    Calculates probability of hitting.
    Returns both the calculation and a roll result.
    """
    attack_roll = roll(20, modifier=attacker_skill // 3)
    total_attack = attack_roll["total"]
    defense_threshold = difficulty_class + (defender_defense // 4)

    hit = total_attack >= defense_threshold
    margin = total_attack - defense_threshold

    return {
        "attack_roll": total_attack,
        "defense_threshold": defense_threshold,
        "hit": hit,
        "critical_hit": attack_roll["is_critical_success"],
        "critical_miss": attack_roll["is_critical_failure"],
        "margin": margin,
    }


def calculate_damage(
    base_damage: int,
    strength_bonus: int,
    weapon_type: str = "sword",
    is_critical: bool = False,
) -> dict:
    """
    Calculates damage dealt.
    Critical hits deal double dice damage.
    """
    weapon_dice = {
        "sword": (6, 1),
        "dagger": (4, 1),
        "axe": (8, 1),
        "mace": (6, 1),
        "bow": (6, 1),
        "staff": (4, 1),
        "fists": (4, 1),
        "spear": (8, 1),
        "greataxe": (12, 1),
        "crossbow": (8, 1),
    }

    sides, count = weapon_dice.get(weapon_type, (6, 1))

    if is_critical:
        count *= 2

    damage_roll = roll(sides, count, modifier=strength_bonus)
    total = max(1, damage_roll["total"])

    return {
        "dice_roll": damage_roll["rolls"],
        "strength_bonus": strength_bonus,
        "total_damage": total,
        "is_critical": is_critical,
        "weapon": weapon_type,
    }


def skill_check(
    skill_value: int,
    difficulty: int,
    advantage: bool = False,
    disadvantage: bool = False,
) -> dict:
    """
    Standard skill check against a difficulty class.

    Advantage: roll twice, take higher
    Disadvantage: roll twice, take lower
    """
    if advantage:
        roll1 = roll(20)["total"]
        roll2 = roll(20)["total"]
        base_roll = max(roll1, roll2)
        rolls_made = [roll1, roll2]
    elif disadvantage:
        roll1 = roll(20)["total"]
        roll2 = roll(20)["total"]
        base_roll = min(roll1, roll2)
        rolls_made = [roll1, roll2]
    else:
        base = roll(20)
        base_roll = base["total"]
        rolls_made = [base_roll]

    total = base_roll + (skill_value // 2)
    success = total >= difficulty
    margin = total - difficulty

    degree = _success_degree(margin, success)

    return {
        "skill_value": skill_value,
        "difficulty": difficulty,
        "rolls": rolls_made,
        "base_roll": base_roll,
        "total": total,
        "success": success,
        "degree": degree,
        "margin": margin,
        "had_advantage": advantage,
        "had_disadvantage": disadvantage,
    }


def _success_degree(margin: int, success: bool) -> str:
    if not success:
        if margin <= -10:
            return "critical_failure"
        else:
            return "failure"
    else:
        if margin >= 10:
            return "critical_success"
        elif margin >= 5:
            return "great_success"
        else:
            return "success"