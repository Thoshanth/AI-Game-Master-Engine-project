import json
import random
import uuid
from pathlib import Path
from datetime import datetime
from backend.combat.dice_engine import (
    roll,
    roll_initiative,
    calculate_hit_chance,
    calculate_damage,
    skill_check,
)
from backend.combat.status_effects import (
    apply_status_effect,
    tick_status_effects,
    get_combat_modifiers,
    check_action_triggers_effect,
)
from backend.combat.combat_narrator import (
    narrate_combat_round,
    narrate_combat_end,
)
from backend.database.db import SessionLocal, Player, NPC
from backend.database.world_store import (
    get_player,
    get_npc,
    get_location,
    record_event,
    get_world,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.logger import get_logger

logger = get_logger("combat.resolver")

COMBAT_STORAGE = Path("game_data/active_combats")
COMBAT_STORAGE.mkdir(parents=True, exist_ok=True)

ENEMY_TEMPLATES = {
    "bandit": {
        "hp": 35,
        "max_hp": 35,
        "strength": 12,
        "defense": 8,
        "agility": 10,
        "weapon": "sword",
        "armor": "leather",
        "damage_bonus": 2,
        "attack_skill": 10,
        "loot": ["gold_5-15", "leather_armor", "sword"],
        "flee_threshold": 0.3,
        "description": "A desperate bandit with wild eyes",
    },
    "guard": {
        "hp": 50,
        "max_hp": 50,
        "strength": 14,
        "defense": 12,
        "agility": 9,
        "weapon": "spear",
        "armor": "chainmail",
        "damage_bonus": 3,
        "attack_skill": 14,
        "loot": ["gold_10-20", "iron_key"],
        "flee_threshold": 0.2,
        "description": "A disciplined city guard",
    },
    "wolf": {
        "hp": 25,
        "max_hp": 25,
        "strength": 13,
        "defense": 6,
        "agility": 16,
        "weapon": "fists",
        "armor": "none",
        "damage_bonus": 2,
        "attack_skill": 12,
        "loot": ["wolf_pelt", "wolf_fang"],
        "flee_threshold": 0.4,
        "description": "A snarling grey wolf",
    },
    "skeleton": {
        "hp": 30,
        "max_hp": 30,
        "strength": 10,
        "defense": 10,
        "agility": 8,
        "weapon": "sword",
        "armor": "bone",
        "damage_bonus": 1,
        "attack_skill": 9,
        "loot": ["bone_fragment", "gold_2-8"],
        "flee_threshold": 0.0,
        "description": "An animated skeleton warrior",
    },
    "mage": {
        "hp": 20,
        "max_hp": 20,
        "strength": 7,
        "defense": 6,
        "agility": 12,
        "weapon": "staff",
        "armor": "robe",
        "damage_bonus": 5,
        "attack_skill": 16,
        "loot": ["spellbook", "mana_potion", "gold_20-50"],
        "flee_threshold": 0.5,
        "description": "A robed mage crackling with energy",
    },
    "troll": {
        "hp": 80,
        "max_hp": 80,
        "strength": 18,
        "defense": 14,
        "agility": 6,
        "weapon": "greataxe",
        "armor": "hide",
        "damage_bonus": 6,
        "attack_skill": 12,
        "loot": ["troll_hide", "gold_30-80", "gem_common"],
        "flee_threshold": 0.1,
        "description": "A massive regenerating troll",
    },
}


def save_combat(combat_id: str, state: dict):
    path = COMBAT_STORAGE / f"{combat_id}.json"
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def load_combat(combat_id: str) -> dict:
    path = COMBAT_STORAGE / f"{combat_id}.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def end_combat(combat_id: str):
    path = COMBAT_STORAGE / f"{combat_id}.json"
    if path.exists():
        path.unlink()


def start_combat(
    world_id: int,
    player_id: int,
    enemy_type: str = "bandit",
    enemy_name: str = None,
    location_id: int = None,
    custom_enemy: dict = None,
) -> dict:

    logger.info(
        f"Combat starting | player={player_id} | "
        f"enemy={enemy_type} | world={world_id}"
    )

    player = get_player(player_id)
    if not player:
        return {"error": "Player not found"}

    enemy_template = custom_enemy or ENEMY_TEMPLATES.get(
        enemy_type, ENEMY_TEMPLATES["bandit"]
    )

    enemy = enemy_template.copy()
    enemy["name"] = enemy_name or enemy_type.replace("_", " ").title()
    enemy["type"] = enemy_type
    enemy["effects"] = []

    location = None
    if location_id:
        location = get_location(location_id)

    player_stats = {
        "stealth": player.stealth,
        "strength": player.strength,
    }

    enemy_stats = {
        "agility": enemy.get("agility", 10),
    }

    initiative = roll_initiative(player_stats, enemy_stats)

    world_time = get_current_world_time(world_id)

    combat_id = f"combat_{player_id}_{uuid.uuid4().hex[:8]}"

    combat_state = {
        "combat_id": combat_id,
        "world_id": world_id,
        "player_id": player_id,
        "location_id": location_id,
        "location_name": location.name if location else "Unknown",
        "started_at": datetime.utcnow().isoformat(),
        "world_day": world_time.get("total_days", 0),
        "round": 0,
        "status": "active",
        "player": {
            "name": player.character_name,
            "class": player.character_class,
            "hp": player.health,
            "max_hp": player.max_health,
            "strength": player.strength,
            "intelligence": player.intelligence,
            "charisma": player.charisma,
            "stealth": player.stealth,
            "weapon": "sword",
            "effects": [],
        },
        "enemy": enemy,
        "initiative": initiative,
        "round_log": [],
        "outcome": None,
    }

    save_combat(combat_id, combat_state)

    record_event(
        world_id=world_id,
        event_type="combat",
        title=f"{player.character_name} vs {enemy['name']}",
        description=(
            f"{player.character_name} engages in combat with "
            f"{enemy['name']} at {combat_state['location_name']}."
        ),
        world_day=world_time.get("total_days", 0),
        location_id=location_id,
        player_id=player_id,
        importance=3,
    )

    return {
        "combat_id": combat_id,
        "status": "active",
        "round": 0,
        "initiative": initiative,
        "player": {
            "name": combat_state["player"]["name"],
            "hp": combat_state["player"]["hp"],
            "max_hp": combat_state["player"]["max_hp"],
        },
        "enemy": {
            "name": enemy["name"],
            "description": enemy["description"],
            "hp": enemy["hp"],
        },
        "location": combat_state["location_name"],
        "opening_message": (
            "You strike first!"
            if initiative["player_goes_first"]
            else f"{enemy['name']} acts first!"
        ),
    }


def resolve_round(
    combat_id: str,
    player_action: str = "attack",
    weapon_type: str = None,
) -> dict:

    state = load_combat(combat_id)

    if not state:
        return {"error": "Combat not found"}

    if state["status"] != "active":
        return {"error": "Combat already ended"}

    state["round"] += 1

    player = state["player"]
    enemy = state["enemy"]

    player_mods = get_combat_modifiers(player["effects"])
    enemy_mods = get_combat_modifiers(enemy["effects"])

    if player_mods.get("must_flee"):
        return attempt_flee(combat_id)

    player_goes_first = state["initiative"]["player_goes_first"]

    player_round_result = {
        "hit": False,
        "damage": 0,
        "critical_hit": False,
        "critical_miss": False,
        "new_effects": [],
    }

    enemy_round_result = {
        "hit": False,
        "damage": 0,
        "critical_hit": False,
        "critical_miss": False,
        "new_effects": [],
    }

    weapon = weapon_type or player.get("weapon", "sword")

    def do_player_attack():
        if not player_mods.get("can_act", True):
            return

        attack_skill = (
            player["strength"]
            + player_mods.get("attack_bonus", 0)
            - player_mods.get("attack_penalty", 0)
        )

        hit_result = calculate_hit_chance(
            attacker_skill=attack_skill,
            defender_defense=enemy.get("defense", 10),
        )

        player_round_result["hit"] = hit_result["hit"]

        if hit_result["hit"]:
            dmg = calculate_damage(
                base_damage=10,
                strength_bonus=player["strength"] // 4,
                weapon_type=weapon,
                is_critical=hit_result["critical_hit"],
            )

            actual_damage = max(1, dmg["total_damage"])

            player_round_result["damage"] = actual_damage
            enemy["hp"] -= actual_damage

    def do_enemy_attack():
        if not enemy_mods.get("can_act", True):
            return

        hit_result = calculate_hit_chance(
            attacker_skill=enemy.get("attack_skill", 10),
            defender_defense=player["stealth"] // 2,
        )

        enemy_round_result["hit"] = hit_result["hit"]

        if hit_result["hit"]:
            dmg = calculate_damage(
                base_damage=8,
                strength_bonus=enemy.get("strength", 10) // 4,
                weapon_type=enemy.get("weapon", "sword"),
            )

            actual_damage = max(1, dmg["total_damage"])

            enemy_round_result["damage"] = actual_damage
            player["hp"] -= actual_damage

    if player_goes_first:
        do_player_attack()
        if enemy["hp"] > 0:
            do_enemy_attack()
    else:
        do_enemy_attack()
        if player["hp"] > 0:
            do_player_attack()

    # FIXED CONDITION HERE
    if (
        enemy["hp"] / enemy["max_hp"]
        < enemy.get("flee_threshold", 0.3)
        and random.random() < 0.4
    ):
        state["status"] = "ended"
        state["outcome"] = "enemy_fled"

    save_combat(combat_id, state)

    return {
        "combat_id": combat_id,
        "round": state["round"],
        "status": state["status"],
        "player_hp": player["hp"],
        "enemy_hp": enemy["hp"],
    }


def attempt_flee(combat_id: str) -> dict:

    state = load_combat(combat_id)

    if not state:
        return {"error": "Combat not found"}

    player = state["player"]
    enemy = state["enemy"]

    flee_check = skill_check(
        skill_value=player["stealth"],
        difficulty=10 + enemy.get("agility", 10) // 3,
    )

    if flee_check["success"]:
        state["status"] = "ended"
        state["outcome"] = "player_fled"

        end_combat(combat_id)

        return {
            "fled": True,
            "status": "ended",
            "outcome": "player_fled",
        }

    return {
        "fled": False,
        "status": "active",
        "player_hp": player["hp"],
    }