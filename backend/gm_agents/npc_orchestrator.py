import json
import random
from backend.database.db import SessionLocal, NPC
from backend.database.world_store import (
    get_npcs_at_location, get_npc, get_location,
)
from backend.npc_memory.memory_store import (
    retrieve_relevant_memories, get_memory_count,
)
from backend.npc_memory.relationship_engine import (
    get_npc_relationship_with_player,
)
from backend.npc_memory.emotion_engine import get_emotion_description
from backend.logger import get_logger

logger = get_logger("gm_agents.npc_orchestrator")

# Conditions under which an NPC proactively approaches a player
PROACTIVE_CONDITIONS = [
    {
        "name": "quest_giver_urgent",
        "condition": lambda npc, rel, mem_count: (
            npc.role == "quest_giver" and mem_count == 0
        ),
        "reason": "Quest giver has never met player",
        "approach": "urgent_approach",
    },
    {
        "name": "grateful_npc_rewards",
        "condition": lambda npc, rel, mem_count: (
            rel > 0.6 and npc.emotion_state == "grateful"
        ),
        "reason": "Grateful NPC wants to thank player",
        "approach": "friendly_approach",
    },
    {
        "name": "hostile_npc_confronts",
        "condition": lambda npc, rel, mem_count: (
            rel < -0.5 and npc.emotion_state in [
                "angry", "hostile"
            ]
        ),
        "reason": "Hostile NPC confronts player",
        "approach": "confrontational",
    },
    {
        "name": "informed_npc_shares_rumor",
        "condition": lambda npc, rel, mem_count: (
            rel > 0.2 and mem_count > 3
        ),
        "reason": "Friendly NPC wants to share information",
        "approach": "information_share",
    },
]


def npc_orchestrator_agent(state: dict) -> dict:
    """
    Agent 3 — NPC Orchestrator

    Coordinates NPC behavior across the world.
    Decides which NPCs act proactively toward the player.

    Uses Stage 3 NPC memory and relationships to ensure
    NPC behavior is consistent with their history.

    Reads:  world_id, player_id, scene_description, content_plan
    Writes: npc_directives, proactive_npcs, npc_reactions
    """
    world_id = state["world_id"]
    player_id = state["player_id"]
    trigger_data = state.get("trigger_data", {})
    content_plan = state.get("content_plan", {})
    iteration = state.get("iterations", 0)

    logger.info(
        f"NPC Orchestrator | world={world_id} | "
        f"player={player_id} | iter={iteration}"
    )

    location_id = trigger_data.get("location_id")
    npc_directives = []
    proactive_npcs = []
    npc_reactions = []

    if not location_id:
        return {
            "npc_directives": [],
            "proactive_npcs": [],
            "npc_reactions": [],
            "agent_log": state.get("agent_log", []) + [{
                "agent": "NPCOrchestrator",
                "note": "No location specified",
            }],
        }

    # Get NPCs at location
    db = SessionLocal()
    try:
        npcs_at_location = db.query(NPC).filter(
            NPC.location_id == location_id,
            NPC.is_alive == True,
        ).all()

        for npc in npcs_at_location[:8]:
            # Get relationship with player
            rel_data = get_npc_relationship_with_player(
                npc.id, player_id
            )
            rel_score = rel_data.get("relationship_score", 0.0)

            # Get memory count
            mem_count = get_memory_count(npc.id)

            # Check proactive conditions
            for condition in PROACTIVE_CONDITIONS:
                try:
                    if condition["condition"](npc, rel_score, mem_count):
                        proactive_npcs.append({
                            "npc_id": npc.id,
                            "npc_name": npc.name,
                            "role": npc.role,
                            "reason": condition["reason"],
                            "approach_type": condition["approach"],
                            "relationship_score": rel_score,
                            "emotion": npc.emotion_state,
                        })
                        break
                except Exception:
                    pass

            # Generate NPC reaction to trigger
            emotion_desc = get_emotion_description(
                npc.emotion_state,
                npc.emotion_intensity,
                npc.trait_extraversion,
            )

            reaction = _generate_npc_reaction(
                npc, rel_score, emotion_desc,
                state.get("trigger", ""),
                content_plan,
            )

            if reaction:
                npc_reactions.append({
                    "npc_id": npc.id,
                    "npc_name": npc.name,
                    "reaction": reaction,
                    "emotion": npc.emotion_state,
                })

    finally:
        db.close()

    # Sort proactive NPCs by priority
    proactive_npcs.sort(
        key=lambda x: abs(x["relationship_score"]),
        reverse=True,
    )

    # Build directives for most important NPC interactions
    for npc_info in proactive_npcs[:3]:
        directive = {
            "npc_id": npc_info["npc_id"],
            "npc_name": npc_info["npc_name"],
            "directive": npc_info["approach_type"],
            "reason": npc_info["reason"],
            "priority": (
                "high" if abs(npc_info["relationship_score"]) > 0.5
                else "normal"
            ),
        }
        npc_directives.append(directive)

    logger.info(
        f"NPC Orchestrator complete | "
        f"npcs_checked={len(npcs_at_location if location_id else [])} | "
        f"proactive={len(proactive_npcs)} | "
        f"reactions={len(npc_reactions)}"
    )

    return {
        "npc_directives": npc_directives,
        "proactive_npcs": proactive_npcs[:5],
        "npc_reactions": npc_reactions[:5],
        "agent_log": state.get("agent_log", []) + [{
            "agent": "NPCOrchestrator",
            "iteration": iteration,
            "npcs_at_location": len(
                npcs_at_location if location_id else []
            ),
            "proactive_count": len(proactive_npcs),
        }],
    }


def _generate_npc_reaction(
    npc: NPC,
    relationship: float,
    emotion_desc: str,
    trigger: str,
    content_plan: dict,
) -> str | None:
    """Generates a brief NPC reaction to the current situation."""
    if npc.trait_extraversion < 3:
        if random.random() < 0.7:
            return None

    reactions = {
        "player_entered_location": {
            "friendly": (
                f"{npc.name} looks up and nods in recognition."
            ),
            "hostile": (
                f"{npc.name} stiffens as you enter, hand moving "
                f"toward their weapon."
            ),
            "neutral": (
                f"{npc.name} glances up briefly then returns "
                f"to their work."
            ),
        },
        "player_completed_quest": {
            "friendly": (
                f"{npc.name} breaks into a genuine smile. "
                f"Word travels fast here."
            ),
            "hostile": (
                f"{npc.name} looks irritated by your success."
            ),
            "neutral": (
                f"{npc.name} acknowledges your accomplishment "
                f"with a brief nod."
            ),
        },
    }

    relationship_tier = (
        "friendly" if relationship > 0.2
        else "hostile" if relationship < -0.2
        else "neutral"
    )

    trigger_reactions = reactions.get(trigger, {})
    return trigger_reactions.get(relationship_tier)