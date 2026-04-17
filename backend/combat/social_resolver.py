from backend.combat.dice_engine import skill_check
from backend.combat.combat_narrator import narrate_social
from backend.npc_memory.relationship_engine import (
    get_npc_relationship_with_player,
    update_relationship_score,
    get_relationship_info,
)
from backend.npc_memory.emotion_engine import update_npc_emotion
from backend.npc_memory.memory_store import store_memory
from backend.database.world_store import get_player, get_npc
from backend.world_engine.world_clock import get_current_world_time
from backend.logger import get_logger

logger = get_logger("combat.social")

# Social interaction types and base difficulties
SOCIAL_INTERACTIONS = {
    "persuade": {
        "stat": "charisma",
        "base_dc": 13,
        "success_rel_delta": 0.1,
        "failure_rel_delta": -0.05,
        "critical_success_emotion": "grateful",
        "critical_failure_emotion": "angry",
    },
    "intimidate": {
        "stat": "strength",
        "base_dc": 12,
        "success_rel_delta": -0.1,
        "failure_rel_delta": -0.15,
        "critical_success_emotion": "fearful",
        "critical_failure_emotion": "hostile",
    },
    "deceive": {
        "stat": "charisma",
        "base_dc": 14,
        "success_rel_delta": 0.0,
        "failure_rel_delta": -0.2,
        "critical_success_emotion": "neutral",
        "critical_failure_emotion": "hostile",
    },
    "inspire": {
        "stat": "charisma",
        "base_dc": 11,
        "success_rel_delta": 0.15,
        "failure_rel_delta": 0.0,
        "critical_success_emotion": "excited",
        "critical_failure_emotion": "neutral",
    },
    "bribe": {
        "stat": "charisma",
        "base_dc": 10,
        "success_rel_delta": 0.05,
        "failure_rel_delta": -0.1,
        "critical_success_emotion": "happy",
        "critical_failure_emotion": "suspicious",
    },
}


def resolve_social_interaction(
    world_id: int,
    player_id: int,
    npc_id: int,
    interaction_type: str,
    approach_description: str = "",
) -> dict:
    """
    Resolves a social interaction between player and NPC.

    Factors affecting outcome:
    - Player charisma/strength stat
    - Current relationship score (friendly = easier)
    - NPC personality (agreeableness, neuroticism)
    - NPC current emotion (happy NPC = easier to persuade)

    Updates relationship score and NPC emotion based on result.
    """
    logger.info(
        f"Social check | player={player_id} | "
        f"npc={npc_id} | type={interaction_type}"
    )

    player = get_player(player_id)
    npc = get_npc(npc_id)

    if not player or not npc:
        return {"error": "Player or NPC not found"}

    if interaction_type not in SOCIAL_INTERACTIONS:
        return {
            "error": f"Unknown interaction: {interaction_type}",
            "valid": list(SOCIAL_INTERACTIONS.keys()),
        }

    config = SOCIAL_INTERACTIONS[interaction_type]

    # Get relevant stat
    stat_name = config["stat"]
    stat_value = getattr(player, stat_name, 10)

    # Get relationship modifiers
    relationship = get_npc_relationship_with_player(npc_id, player_id)
    rel_score = relationship.get("relationship_score", 0.0)
    rel_info = get_relationship_info(rel_score)

    # Relationship bonus: friendly = +4, hostile = -4
    rel_bonus = int(rel_score * 6)

    # NPC personality modifiers
    agreeableness_bonus = int((npc.trait_agreeableness - 5) * 0.5)
    neuroticism_penalty = int((npc.trait_neuroticism - 5) * 0.3)

    # Emotion modifier
    emotion_mods = {
        "happy": 2, "grateful": 3, "excited": 2,
        "neutral": 0, "suspicious": -2,
        "angry": -4, "hostile": -6, "fearful": -1,
    }
    emotion_bonus = emotion_mods.get(npc.emotion_state, 0)

    # Calculate effective DC
    base_dc = config["base_dc"]
    effective_dc = max(
        5,
        base_dc - rel_bonus - agreeableness_bonus +
        neuroticism_penalty - emotion_bonus,
    )

    # Roll check
    result = skill_check(
        skill_value=stat_value,
        difficulty=effective_dc,
    )

    degree = result["degree"]
    success = result["success"]

    # Calculate relationship change
    if success:
        rel_delta = config["success_rel_delta"]
        if degree == "critical_success":
            rel_delta *= 2
        new_emotion = config["critical_success_emotion"]
    else:
        rel_delta = config["failure_rel_delta"]
        if degree == "critical_failure":
            rel_delta *= 2
        new_emotion = config["critical_failure_emotion"]

    # Update NPC state
    update_relationship_score(npc_id, player_id, rel_delta)
    action_map = {
        "persuade": "player_complimented",
        "intimidate": "player_threatened",
        "deceive": "player_lied",
        "inspire": "player_helped",
        "bribe": "player_gave_gift",
    }
    update_npc_emotion(
        npc_id,
        action_map.get(interaction_type, "player_questioned"),
    )

    # Store memory
    world_time = get_current_world_time(world_id)
    memory_text = (
        f"{player.character_name} attempted to {interaction_type} me. "
        f"Outcome: {degree}. "
        f"Approach: {approach_description[:80] if approach_description else 'standard'}."
    )
    store_memory(
        npc_id=npc_id,
        memory_text=memory_text,
        player_id=player_id,
        event_type=f"social_{interaction_type}",
        emotion_at_time=new_emotion,
        relationship_delta=rel_delta,
        world_day=world_time.get("total_days", 0),
        importance=5,
    )

    # Generate narration
    npc_personality = (
        f"agreeableness {npc.trait_agreeableness:.0f}/10, "
        f"currently {npc.emotion_state}"
    )
    narration = narrate_social(
        player_name=player.character_name,
        npc_name=npc.name,
        social_type=interaction_type,
        degree=degree,
        npc_personality=npc_personality,
    )

    logger.info(
        f"Social resolved | "
        f"degree={degree} | rel_delta={rel_delta:+.2f}"
    )

    return {
        "interaction_type": interaction_type,
        "degree": degree,
        "success": success,
        "stat_used": stat_name,
        "stat_value": stat_value,
        "roll": result["base_roll"],
        "total": result["total"],
        "effective_dc": effective_dc,
        "narration": narration,
        "relationship_change": {
            "delta": rel_delta,
            "new_label": rel_info["label"],
        },
        "npc_new_emotion": new_emotion,
        "modifiers_applied": {
            "relationship_bonus": rel_bonus,
            "agreeableness_bonus": agreeableness_bonus,
            "emotion_bonus": emotion_bonus,
        },
    }