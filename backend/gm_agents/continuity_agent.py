import json
from backend.llm_client import chat_completion_json
from backend.database.world_store import (
    get_world_summary, get_factions, get_recent_events,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.simulation.economy_engine import get_current_prices
from backend.logger import get_logger

logger = get_logger("gm_agents.continuity")


def continuity_agent(state: dict) -> dict:
    """
    Agent 5 — World Continuity Agent

    Reviews all other agents' outputs and checks for:
    - Contradictions with established world facts
    - Economic inconsistencies (thriving city in depression)
    - NPC behavior contradictions (hostile NPC acting friendly)
    - Timeline impossibilities
    - Tone inconsistencies

    Can approve or request specific agent revisions.

    Reads:  ALL previous agent outputs
    Writes: continuity_approved, continuity_issues, revision_needed
    """
    world_id = state["world_id"]
    iteration = state.get("iterations", 0)

    logger.info(
        f"Continuity Agent | world={world_id} | iter={iteration}"
    )

    scene_description = state.get("scene_description", "")
    content_plan = state.get("content_plan", {})
    npc_directives = state.get("npc_directives", [])
    conflict_resolution = state.get("conflict_resolution", {})

    # Get world facts to check against
    world_summary = get_world_summary(world_id)
    world_time = get_current_world_time(world_id)
    factions = get_factions(world_id)
    recent_events = get_recent_events(
        world_id, limit=5, notable_only=True
    )

    # Fast checks (no LLM needed)
    issues = []

    # Check 1: Economic consistency
    try:
        prices = get_current_prices(world_id)
        high_inflation = sum(
            1 for p in prices.values()
            if p.get("price_trend") in ["very_high", "high"]
        )
        if high_inflation > 10 and "thriving" in scene_description.lower():
            issues.append({
                "type": "economic_inconsistency",
                "description": (
                    "Scene describes thriving conditions but "
                    "economy shows high inflation"
                ),
                "severity": "moderate",
                "target_agent": "narrator",
            })
    except Exception as e:
        logger.warning(f"Economy check failed: {e}")

    # Check 2: Faction war consistency
    from backend.database.db import SessionLocal, FactionRelationship
    db = SessionLocal()
    try:
        wars = db.query(FactionRelationship).filter(
            FactionRelationship.world_id == world_id,
            FactionRelationship.relation == "at_war",
        ).count()

        if wars > 0 and "peaceful" in scene_description.lower():
            issues.append({
                "type": "war_inconsistency",
                "description": (
                    f"Scene describes peace but "
                    f"{wars} faction war(s) are active"
                ),
                "severity": "major",
                "target_agent": "narrator",
            })
    finally:
        db.close()

    # Check 3: NPC behavior consistency
    for directive in npc_directives:
        if (directive.get("directive") == "friendly_approach" and
                directive.get("relationship_score", 0) < -0.3):
            issues.append({
                "type": "npc_behavior_inconsistency",
                "description": (
                    f"{directive.get('npc_name')} is directed to "
                    f"approach friendly but has negative relationship"
                ),
                "severity": "minor",
                "target_agent": "npc_orchestrator",
            })

    # LLM deep check for complex inconsistencies
    if len(issues) == 0:
        issues = _llm_continuity_check(
            state, world_summary, world_time, factions,
        )

    # Determine if revision needed
    major_issues = [
        i for i in issues if i.get("severity") == "major"
    ]
    revision_needed = (
        len(major_issues) > 0 and
        iteration < state.get("max_iterations", 2)
    )

    # Determine which agent needs to revise
    revision_target = ""
    if revision_needed and major_issues:
        revision_target = major_issues[0].get("target_agent", "narrator")

    # Compile final response
    final_response = _compile_final_response(state)

    approved = not revision_needed

    logger.info(
        f"Continuity Agent complete | "
        f"issues={len(issues)} | "
        f"major={len(major_issues)} | "
        f"approved={approved}"
    )

    return {
        "continuity_approved": approved,
        "continuity_issues": issues,
        "revision_needed": revision_needed,
        "revision_target": revision_target,
        "iterations": iteration + 1,
        "final_response": final_response,
        "agent_log": state.get("agent_log", []) + [{
            "agent": "Continuity",
            "iteration": iteration,
            "issues": len(issues),
            "major_issues": len(major_issues),
            "approved": approved,
        }],
    }


def _llm_continuity_check(
    state: dict,
    world_summary: dict,
    world_time: dict,
    factions: list,
) -> list:
    """Uses LLM for deeper continuity checking."""
    try:
        scene = state.get("scene_description", "")[:300]
        faction_names = [f.name for f in factions[:3]]
        stats = world_summary.get("statistics", {})

        prompt = f"""Check this RPG scene for continuity issues.

Scene: {scene}
World stats: {json.dumps(stats, indent=2)}
Active factions: {', '.join(faction_names)}
Current time: {world_time.get('time_string', 'unknown')}

List any factual inconsistencies as JSON array.
If no issues, return empty array.

Return ONLY:
[
    {{
        "type": "issue_type",
        "description": "what is inconsistent",
        "severity": "minor|moderate|major",
        "target_agent": "narrator|npc_orchestrator|content_director"
    }}
]"""

        raw = chat_completion_json(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )

        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        result = json.loads(cleaned.strip())
        return result if isinstance(result, list) else []

    except Exception as e:
        logger.warning(f"LLM continuity check failed: {e}")
        return []


def _compile_final_response(state: dict) -> str:
    """Compiles all agent outputs into the final GM response."""
    parts = []

    scene = state.get("scene_description", "")
    if scene:
        parts.append(scene)

    npc_reactions = state.get("npc_reactions", [])
    if npc_reactions:
        reactions_text = "\n".join(
            r.get("reaction", "") for r in npc_reactions[:3]
            if r.get("reaction")
        )
        if reactions_text:
            parts.append(reactions_text)

    proactive_npcs = state.get("proactive_npcs", [])
    if proactive_npcs:
        top_npc = proactive_npcs[0]
        parts.append(
            f"[{top_npc['npc_name']} wants to speak with you — "
            f"{top_npc['reason']}]"
        )

    conflict = state.get("conflict_resolution", {})
    if conflict and state.get("conflict_detected"):
        parts.append(
            f"\n⚔️ {conflict.get('conflict_summary', 'A conflict is brewing')}"
        )

    hooks = state.get("upcoming_hooks", [])
    if hooks:
        parts.append(f"\n💡 {hooks[0]}")

    return "\n\n".join(parts)