from backend.llm_client import chat_completion
from backend.procedural.world_context import build_world_context_string
from backend.logger import get_logger

logger = get_logger("combat.narrator")


def narrate_combat_round(
    world_id: int,
    round_number: int,
    player_name: str,
    enemy_name: str,
    player_action: str,
    enemy_action: str,
    player_result: dict,
    enemy_result: dict,
    player_hp: int,
    enemy_hp: int,
    player_effects: list,
    enemy_effects: list,
    location_name: str = "unknown location",
) -> str:
    """
    Generates vivid narrative for a combat round
    using the LLM with full context.
    """
    player_status = _build_combatant_status(
        player_name, player_hp, player_effects
    )
    enemy_status = _build_combatant_status(
        enemy_name, enemy_hp, enemy_effects
    )

    hit_desc = _hit_description(player_result)
    enemy_hit_desc = _hit_description(enemy_result)

    effects_str = ""
    if player_result.get("new_effects"):
        effects_str += (
            f"New effects on {enemy_name}: "
            f"{', '.join(player_result['new_effects'])}. "
        )
    if enemy_result.get("new_effects"):
        effects_str += (
            f"New effects on {player_name}: "
            f"{', '.join(enemy_result['new_effects'])}."
        )

    prompt = f"""You are narrating a combat scene in a dark fantasy RPG.
Location: {location_name}
Round: {round_number}

WHAT MECHANICALLY HAPPENED:
{player_name} attacks {enemy_name}: {hit_desc}
{enemy_name} attacks {player_name}: {enemy_hit_desc}
{effects_str}

CURRENT STATE:
{player_status}
{enemy_status}

Write 2-4 sentences of vivid combat narration.
Requirements:
- Match the mechanical outcome exactly
- Use specific physical details (where the blow landed, sound, sensation)
- Show the momentum shift if there is one
- Reflect the location atmosphere
- If a critical hit/miss occurred, make it dramatic
- Keep the dark fantasy tone
- Do NOT repeat health numbers — show through description
- End with a sentence that sets up tension for next round

Write the narration now:"""

    try:
        narration = chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a master combat narrator for a dark "
                        "fantasy RPG. Write vivid, immersive narration."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.8,
        )
        return narration.strip()
    except Exception as e:
        logger.warning(f"Narration failed: {e}")
        return _fallback_narration(
            player_name, enemy_name,
            player_result, enemy_result,
        )


def narrate_combat_end(
    player_name: str,
    enemy_name: str,
    outcome: str,
    final_player_hp: int,
    loot: list = None,
    world_id: int = None,
) -> str:
    """Narrates the end of combat."""
    loot_str = (
        f"You find: {', '.join(loot)}" if loot else ""
    )

    prompt = f"""Narrate the end of a combat in 2-3 sentences.

Outcome: {outcome} (player_victory|player_defeat|enemy_fled|player_fled)
{player_name} has {final_player_hp} HP remaining.
{loot_str}

Write the ending narration:"""

    try:
        return chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.8,
        ).strip()
    except Exception as e:
        logger.warning(f"End narration failed: {e}")
        return _fallback_end_narration(outcome, player_name)


def narrate_skill_check(
    player_name: str,
    skill_type: str,
    degree: str,
    difficulty: str,
    context: str = "",
) -> str:
    """Narrates a skill check outcome."""
    prompt = f"""Narrate a skill check in 1-2 sentences.

Player: {player_name}
Skill: {skill_type}
Outcome: {degree} (critical_success|great_success|success|failure|critical_failure)
Difficulty: {difficulty}
Context: {context}

Write vivid narration that matches the outcome exactly:"""

    try:
        return chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.8,
        ).strip()
    except Exception as e:
        logger.warning(f"Skill narration failed: {e}")
        return f"You attempt {skill_type} with {degree} results."


def narrate_social(
    player_name: str,
    npc_name: str,
    social_type: str,
    degree: str,
    npc_personality: str = "",
) -> str:
    """Narrates a social interaction outcome."""
    prompt = f"""Narrate a social interaction in 2-3 sentences.

Player: {player_name}
NPC: {npc_name}
Interaction type: {social_type} (persuade|intimidate|deceive|seduce|inspire)
Outcome: {degree}
NPC personality: {npc_personality}

Include what the NPC says or does in response.
Write vivid narration:"""

    try:
        return chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.8,
        ).strip()
    except Exception as e:
        logger.warning(f"Social narration failed: {e}")
        return f"{npc_name} responds to your {social_type} attempt."


def _hit_description(result: dict) -> str:
    if result.get("critical_hit"):
        return f"CRITICAL HIT for {result.get('damage', 0)} damage"
    elif result.get("critical_miss"):
        return "CRITICAL MISS — stumbles badly"
    elif result.get("hit"):
        return f"HIT for {result.get('damage', 0)} damage"
    else:
        return "MISS"


def _build_combatant_status(
    name: str,
    hp: int,
    effects: list,
) -> str:
    effects_str = (
        ", ".join(e.get("name", "") for e in effects[:3])
        if effects else "none"
    )
    condition = (
        "critically wounded" if hp < 20
        else "badly hurt" if hp < 50
        else "wounded" if hp < 75
        else "lightly wounded" if hp < 90
        else "fresh"
    )
    return (
        f"{name}: {condition} ({hp} HP), "
        f"status effects: {effects_str}"
    )


def _fallback_narration(
    player_name: str,
    enemy_name: str,
    player_result: dict,
    enemy_result: dict,
) -> str:
    lines = []
    if player_result.get("hit"):
        lines.append(
            f"{player_name} strikes {enemy_name} for "
            f"{player_result.get('damage', 0)} damage."
        )
    else:
        lines.append(f"{player_name}'s attack misses.")

    if enemy_result.get("hit"):
        lines.append(
            f"{enemy_name} retaliates for "
            f"{enemy_result.get('damage', 0)} damage."
        )
    else:
        lines.append(f"{enemy_name} fails to land a blow.")

    return " ".join(lines)


def _fallback_end_narration(outcome: str, player_name: str) -> str:
    outcomes = {
        "player_victory": (
            f"{player_name} stands victorious over the fallen enemy."
        ),
        "player_defeat": (
            f"{player_name} falls, defeated and wounded."
        ),
        "enemy_fled": "The enemy flees into the darkness.",
        "player_fled": f"{player_name} escapes the battle.",
    }
    return outcomes.get(outcome, "The battle ends.")