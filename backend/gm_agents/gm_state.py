from typing import Annotated
import operator


class GMState(dict):
    """
    Shared state passed between all 5 GM agents.
    Uses dict subclass for LangGraph compatibility.

    Each agent reads the full state and
    writes to their designated section.
    """
    pass


def create_initial_gm_state(
    world_id: int,
    player_id: int,
    trigger: str,
    trigger_data: dict = None,
) -> GMState:
    """Creates a fresh GM state for a new trigger."""
    return GMState({
        # Input
        "world_id": world_id,
        "player_id": player_id,
        "trigger": trigger,
        "trigger_data": trigger_data or {},

        # Agent 1 — World Narrator
        "scene_description": "",
        "atmosphere": "",
        "sensory_details": [],

        # Agent 2 — Content Director
        "content_plan": {},
        "immediate_events": [],
        "upcoming_hooks": [],
        "recommended_content_type": "",

        # Agent 3 — NPC Orchestrator
        "npc_directives": [],
        "proactive_npcs": [],
        "npc_reactions": [],

        # Agent 4 — Conflict Resolver
        "conflict_detected": False,
        "conflict_resolution": {},
        "conflict_parties": [],

        # Agent 5 — Continuity
        "continuity_approved": False,
        "continuity_issues": [],
        "revision_needed": False,
        "revision_target": "",

        # Control
        "iterations": 0,
        "max_iterations": 2,
        "agent_log": [],

        # Output
        "final_response": "",
        "response_type": "",
        "requires_player_action": False,
        "suggested_actions": [],
    })