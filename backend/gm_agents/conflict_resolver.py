import json
from backend.llm_client import chat_completion_json
from backend.procedural.world_context import build_world_context_string
from backend.database.world_store import get_factions, get_npc
from backend.npc_memory.relationship_engine import (
    get_npc_relationship_with_player,
)
from backend.logger import get_logger

logger = get_logger("gm_agents.conflict")

CONFLICT_TRIGGERS = [
    "multiple_factions_involved",
    "npc_demands_conflict",
    "player_caught_between_parties",
    "moral_dilemma_detected",
    "simultaneous_quest_conflict",
]


def conflict_resolver_agent(state: dict) -> dict:
    """
    Agent 4 — Conflict Resolver

    Handles complex multi-party situations that
    don't fit simple success/failure resolution.

    Only activates when conflict is detected in the scene.

    Reads:  scene_description, npc_directives, content_plan
    Writes: conflict_detected, conflict_resolution
    """
    world_id = state["world_id"]
    player_id = state["player_id"]
    trigger_data = state.get("trigger_data", {})
    npc_directives = state.get("npc_directives", [])
    iteration = state.get("iterations", 0)

    logger.info(
        f"Conflict Resolver | world={world_id} | iter={iteration}"
    )

    # Detect if conflict exists
    conflict_detected = _detect_conflict(
        npc_directives, trigger_data, state
    )

    if not conflict_detected:
        return {
            "conflict_detected": False,
            "conflict_resolution": {},
            "conflict_parties": [],
            "agent_log": state.get("agent_log", []) + [{
                "agent": "ConflictResolver",
                "conflict_detected": False,
            }],
        }

    logger.info("Conflict detected — generating resolution options")

    world_context = build_world_context_string(world_id)
    factions = get_factions(world_id)
    faction_names = [f.name for f in factions]

    # Identify conflict parties
    conflict_parties = []
    hostile_npcs = [
        d for d in npc_directives
        if d.get("directive") == "confrontational"
    ]
    for npc_directive in hostile_npcs[:3]:
        conflict_parties.append({
            "type": "npc",
            "id": npc_directive["npc_id"],
            "name": npc_directive["npc_name"],
            "stance": "hostile",
        })

    prompt = f"""{world_context}

A conflict situation is developing in the RPG world.

Conflict parties: {json.dumps(conflict_parties, indent=2)}
Active factions: {', '.join(faction_names)}
Scene trigger: {state.get('trigger', 'unknown')}
Scene description: {state.get('scene_description', '')[:300]}

Generate fair resolution options for this conflict.

Return ONLY valid JSON:
{{
    "conflict_summary": "1 sentence describing the conflict",
    "conflict_type": "political|personal|faction|moral|resource",
    "resolution_options": [
        {{
            "id": "option_a",
            "description": "How player can resolve this",
            "requires_skill": "combat|persuade|stealth|none",
            "difficulty": "easy|moderate|hard",
            "faction_implications": "which faction benefits",
            "consequence": "what happens if player chooses this"
        }}
    ],
    "time_pressure": "immediate|hours|days|none",
    "escalation_if_ignored": "what happens if player ignores conflict",
    "fair_outcome_if_no_player": "how world resolves without player"
}}

Provide exactly 3 resolution options.
Return valid JSON only."""

    try:
        raw = chat_completion_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an RPG conflict resolution system. "
                        "Return valid JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
        )

        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        resolution = json.loads(cleaned.strip())

        logger.info(
            f"Conflict resolution generated | "
            f"type={resolution.get('conflict_type')} | "
            f"options={len(resolution.get('resolution_options', []))}"
        )

        return {
            "conflict_detected": True,
            "conflict_resolution": resolution,
            "conflict_parties": conflict_parties,
            "agent_log": state.get("agent_log", []) + [{
                "agent": "ConflictResolver",
                "conflict_detected": True,
                "conflict_type": resolution.get("conflict_type"),
                "options": len(
                    resolution.get("resolution_options", [])
                ),
            }],
        }

    except Exception as e:
        logger.error(f"Conflict resolver failed: {e}", exc_info=True)
        return {
            "conflict_detected": True,
            "conflict_resolution": {
                "conflict_summary": "A tense situation is developing",
                "resolution_options": [
                    {
                        "id": "option_a",
                        "description": "Attempt to mediate",
                        "requires_skill": "persuade",
                        "difficulty": "moderate",
                    }
                ],
            },
            "conflict_parties": conflict_parties,
            "agent_log": state.get("agent_log", []) + [{
                "agent": "ConflictResolver",
                "error": str(e),
            }],
        }


def _detect_conflict(
    npc_directives: list,
    trigger_data: dict,
    state: dict,
) -> bool:
    """Detects if a conflict situation exists."""
    # Multiple hostile NPCs = conflict
    hostile_count = sum(
        1 for d in npc_directives
        if d.get("directive") == "confrontational"
    )
    if hostile_count >= 2:
        return True

    # Explicit conflict trigger
    trigger = state.get("trigger", "")
    if "conflict" in trigger or "confrontation" in trigger:
        return True

    # Multiple competing factions in trigger data
    factions_involved = trigger_data.get("factions_involved", [])
    if len(factions_involved) >= 2:
        return True

    return False