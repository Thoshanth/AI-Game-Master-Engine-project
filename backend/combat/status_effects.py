import json
from pathlib import Path
from datetime import datetime
from backend.logger import get_logger

logger = get_logger("combat.status")

# Status effect definitions
STATUS_EFFECTS = {
    "stunned": {
        "description": "Dazed and unable to act effectively",
        "duration_rounds": 1,
        "effects": {
            "attack_penalty": -4,
            "defense_penalty": -4,
            "can_act": False,
        },
        "removal_condition": "end_of_round",
    },
    "bleeding": {
        "description": "Losing blood from a wound",
        "duration_rounds": 3,
        "effects": {
            "hp_per_round": -2,
            "attack_penalty": -1,
        },
        "removal_condition": "medical_treatment_or_duration",
    },
    "poisoned": {
        "description": "Weakened by poison",
        "duration_rounds": 5,
        "effects": {
            "strength_penalty": -2,
            "hp_per_round": -1,
            "attack_penalty": -2,
        },
        "removal_condition": "antidote_or_duration",
    },
    "frightened": {
        "description": "Gripped by fear",
        "duration_rounds": 2,
        "effects": {
            "must_flee": True,
            "attack_penalty": -3,
        },
        "removal_condition": "save_or_duration",
    },
    "inspired": {
        "description": "Filled with confidence",
        "duration_rounds": 3,
        "effects": {
            "attack_bonus": 3,
            "defense_bonus": 2,
            "hp_regen": 1,
        },
        "removal_condition": "duration",
    },
    "blinded": {
        "description": "Cannot see clearly",
        "duration_rounds": 2,
        "effects": {
            "attack_penalty": -5,
            "miss_chance": 0.5,
        },
        "removal_condition": "duration",
    },
    "burning": {
        "description": "On fire",
        "duration_rounds": 3,
        "effects": {
            "hp_per_round": -3,
            "attack_penalty": -2,
        },
        "removal_condition": "water_or_duration",
    },
    "enraged": {
        "description": "In a battle fury",
        "duration_rounds": 4,
        "effects": {
            "attack_bonus": 4,
            "damage_bonus": 3,
            "defense_penalty": -2,
        },
        "removal_condition": "duration",
    },
    "slowed": {
        "description": "Movement and reactions impaired",
        "duration_rounds": 2,
        "effects": {
            "initiative_penalty": -5,
            "attack_penalty": -2,
            "defense_penalty": -2,
        },
        "removal_condition": "duration",
    },
    "shielded": {
        "description": "Protected by a magical or physical barrier",
        "duration_rounds": 3,
        "effects": {
            "defense_bonus": 5,
            "damage_reduction": 3,
        },
        "removal_condition": "duration",
    },
}

# Actions that can trigger status effects
ACTION_STATUS_TRIGGERS = {
    "critical_hit": {
        "chance": 0.4,
        "possible_effects": ["stunned", "bleeding"],
    },
    "fire_attack": {
        "chance": 0.6,
        "possible_effects": ["burning"],
    },
    "poison_weapon": {
        "chance": 0.5,
        "possible_effects": ["poisoned"],
    },
    "intimidate_success": {
        "chance": 0.7,
        "possible_effects": ["frightened"],
    },
    "battle_cry": {
        "chance": 0.8,
        "possible_effects": ["inspired"],
    },
    "rage": {
        "chance": 1.0,
        "possible_effects": ["enraged"],
    },
    "sand_throw": {
        "chance": 0.6,
        "possible_effects": ["blinded"],
    },
}

import random


def apply_status_effect(
    target_effects: list,
    effect_name: str,
) -> list:
    """Applies a status effect to a combatant's effect list."""
    if effect_name not in STATUS_EFFECTS:
        return target_effects

    effect_def = STATUS_EFFECTS[effect_name].copy()
    effect_def["name"] = effect_name
    effect_def["rounds_remaining"] = effect_def["duration_rounds"]
    effect_def["applied_at"] = datetime.utcnow().isoformat()

    # Don't stack same effect
    existing = [e for e in target_effects if e.get("name") != effect_name]
    existing.append(effect_def)

    logger.debug(f"Status effect applied: {effect_name}")
    return existing


def tick_status_effects(effects: list) -> tuple[list, list, int]:
    """
    Advances all status effects by one round.

    Returns:
    - Updated effects list (removed expired ones)
    - List of expired effect names
    - Total HP change from effects this round
    """
    updated = []
    expired = []
    hp_change = 0

    for effect in effects:
        effect["rounds_remaining"] -= 1
        hp_per_round = effect.get("effects", {}).get("hp_per_round", 0)
        hp_change += hp_per_round

        if effect["rounds_remaining"] <= 0:
            expired.append(effect["name"])
        else:
            updated.append(effect)

    return updated, expired, hp_change


def get_combat_modifiers(effects: list) -> dict:
    """Calculates total modifiers from all active status effects."""
    modifiers = {
        "attack_bonus": 0,
        "attack_penalty": 0,
        "defense_bonus": 0,
        "defense_penalty": 0,
        "damage_bonus": 0,
        "damage_reduction": 0,
        "initiative_penalty": 0,
        "miss_chance": 0.0,
        "must_flee": False,
        "can_act": True,
        "hp_regen": 0,
    }

    for effect in effects:
        for stat, value in effect.get("effects", {}).items():
            if stat in modifiers:
                if isinstance(value, bool):
                    modifiers[stat] = modifiers[stat] or value
                elif isinstance(value, float):
                    modifiers[stat] = max(
                        modifiers[stat], value
                    )
                else:
                    modifiers[stat] += value

    return modifiers


def check_action_triggers_effect(
    action_type: str,
    degree: str = "success",
) -> str | None:
    """
    Checks if an action should trigger a status effect.
    Returns effect name or None.
    """
    import random
    trigger = ACTION_STATUS_TRIGGERS.get(action_type)
    if not trigger:
        return None

    if degree == "critical_success":
        chance = trigger["chance"] * 1.5
    elif degree == "critical_failure":
        chance = 0
    else:
        chance = trigger["chance"]

    if random.random() < min(1.0, chance):
        return random.choice(trigger["possible_effects"])

    return None