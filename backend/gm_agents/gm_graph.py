from langgraph.graph import StateGraph, END
from backend.gm_agents.gm_state import GMState
from backend.gm_agents.narrator_agent import narrator_agent
from backend.gm_agents.content_director import content_director_agent
from backend.gm_agents.npc_orchestrator import npc_orchestrator_agent
from backend.gm_agents.conflict_resolver import conflict_resolver_agent
from backend.gm_agents.continuity_agent import continuity_agent
from backend.logger import get_logger

logger = get_logger("gm_agents.graph")


def route_after_conflict(state: dict) -> str:
    """
    After conflict resolver — skip to continuity
    whether conflict was found or not.
    """
    return "continuity"


def route_after_continuity(state: dict) -> str:
    """
    After continuity check:
    - Approved → END
    - Needs revision → back to specific agent
    - Max iterations reached → END
    """
    approved = state.get("continuity_approved", False)
    revision = state.get("revision_needed", False)
    iterations = state.get("iterations", 1)
    max_iter = state.get("max_iterations", 2)

    if approved or not revision or iterations >= max_iter:
        logger.info(
            f"GM routing → END | "
            f"approved={approved} | iter={iterations}"
        )
        return "end"

    target = state.get("revision_target", "narrator")
    logger.info(
        f"GM routing → {target} revision | iter={iterations}"
    )

    revision_map = {
        "narrator": "narrator",
        "npc_orchestrator": "npc_orchestrator",
        "content_director": "content_director",
    }
    return revision_map.get(target, "narrator")


def build_gm_graph():
    """
    Builds the 5-agent Game Master LangGraph.

    Flow:
    START → Narrator → ContentDirector → NPCOrchestrator
          → ConflictResolver → Continuity → END

    Continuity can loop back to any agent for revision (max 2).
    """
    logger.info("Building GM LangGraph")

    workflow = StateGraph(dict)

    # Add all 5 agent nodes
    workflow.add_node("narrator", narrator_agent)
    workflow.add_node("content_director", content_director_agent)
    workflow.add_node("npc_orchestrator", npc_orchestrator_agent)
    workflow.add_node("conflict_resolver", conflict_resolver_agent)
    workflow.add_node("continuity", continuity_agent)

    # Entry point
    workflow.set_entry_point("narrator")

    # Sequential flow
    workflow.add_edge("narrator", "content_director")
    workflow.add_edge("content_director", "npc_orchestrator")
    workflow.add_edge("npc_orchestrator", "conflict_resolver")

    # Conflict → Continuity (always)
    workflow.add_conditional_edges(
        "conflict_resolver",
        route_after_conflict,
        {"continuity": "continuity"},
    )

    # Continuity → conditional routing
    workflow.add_conditional_edges(
        "continuity",
        route_after_continuity,
        {
            "end": END,
            "narrator": "narrator",
            "npc_orchestrator": "npc_orchestrator",
            "content_director": "content_director",
        },
    )

    app = workflow.compile()
    logger.info("GM graph compiled successfully")
    return app


# Build once at module load
gm_graph = build_gm_graph()