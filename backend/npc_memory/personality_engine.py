from backend.database.db import SessionLocal, NPC
from backend.logger import get_logger

logger = get_logger("npc_memory.personality")


def get_personality_profile(npc_id: int) -> dict:
    """
    Returns a complete personality profile for an NPC.
    Used to shape dialogue generation.
    """
    db = SessionLocal()
    try:
        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        if not npc:
            return {}

        return {
            "npc_id": npc_id,
            "npc_name": npc.name,
            "traits": {
                "openness": npc.trait_openness,
                "conscientiousness": npc.trait_conscientiousness,
                "extraversion": npc.trait_extraversion,
                "agreeableness": npc.trait_agreeableness,
                "neuroticism": npc.trait_neuroticism,
            },
            "personality_summary": _build_personality_summary(npc),
            "dialogue_instructions": _build_dialogue_instructions(npc),
            "behavioral_tendencies": _build_behavioral_tendencies(npc),
        }
    finally:
        db.close()


def _build_personality_summary(npc: NPC) -> str:
    """Converts Big Five scores to a natural language summary."""
    traits = []

    if npc.trait_openness >= 7:
        traits.append("curious and open to new ideas")
    elif npc.trait_openness <= 3:
        traits.append("traditional and resistant to change")

    if npc.trait_conscientiousness >= 7:
        traits.append("disciplined and reliable")
    elif npc.trait_conscientiousness <= 3:
        traits.append("spontaneous and disorganized")

    if npc.trait_extraversion >= 7:
        traits.append("outgoing and talkative")
    elif npc.trait_extraversion <= 3:
        traits.append("reserved and introverted")

    if npc.trait_agreeableness >= 7:
        traits.append("compassionate and cooperative")
    elif npc.trait_agreeableness <= 3:
        traits.append("competitive and skeptical of others")

    if npc.trait_neuroticism >= 7:
        traits.append("emotionally volatile and anxious")
    elif npc.trait_neuroticism <= 3:
        traits.append("emotionally stable and calm")

    if not traits:
        return "balanced and average in most personality traits"

    return ", ".join(traits)


def _build_dialogue_instructions(npc: NPC) -> str:
    """
    Builds specific dialogue style instructions for the LLM.
    These make each NPC sound distinctly different.
    """
    instructions = []

    # Extraversion affects verbosity
    if npc.trait_extraversion >= 7:
        instructions.append(
            "Speak enthusiastically. Use long sentences. "
            "Share information freely. Ask follow-up questions."
        )
    elif npc.trait_extraversion <= 3:
        instructions.append(
            "Speak tersely. Use short sentences. "
            "Only say what is necessary. Avoid small talk."
        )
    else:
        instructions.append("Speak normally and conversationally.")

    # Agreeableness affects tone
    if npc.trait_agreeableness >= 7:
        instructions.append(
            "Be warm and accommodating. Give benefit of the doubt. "
            "Use softening language like 'perhaps' and 'I think'."
        )
    elif npc.trait_agreeableness <= 3:
        instructions.append(
            "Be blunt and transactional. "
            "Don't sugarcoat. State things directly."
        )

    # Conscientiousness affects reliability signals
    if npc.trait_conscientiousness >= 7:
        instructions.append(
            "Reference duties and responsibilities. "
            "Be organized in your thoughts. Keep promises."
        )
    elif npc.trait_conscientiousness <= 3:
        instructions.append(
            "Be vague about commitments. "
            "Seem easily distracted. Mention other things you need to do."
        )

    # Neuroticism affects emotional expression
    if npc.trait_neuroticism >= 7:
        instructions.append(
            "Express emotions dramatically. "
            "Worry out loud. React strongly to stress."
        )
    elif npc.trait_neuroticism <= 3:
        instructions.append(
            "Remain calm under pressure. "
            "Understate emotions. Show stoic composure."
        )

    # Openness affects curiosity
    if npc.trait_openness >= 7:
        instructions.append(
            "Show curiosity about the player. "
            "Reference ideas and possibilities. Think creatively."
        )
    elif npc.trait_openness <= 3:
        instructions.append(
            "Be suspicious of unusual requests. "
            "Reference tradition and how things have always been done."
        )

    return " ".join(instructions)


def _build_behavioral_tendencies(npc: NPC) -> dict:
    """Returns behavioral tendency scores for game mechanics."""
    return {
        "likelihood_to_gossip": min(
            1.0,
            (npc.trait_extraversion + (10 - npc.trait_conscientiousness)) / 20.0
        ),
        "likelihood_to_help_stranger": min(
            1.0,
            (npc.trait_agreeableness + npc.trait_openness) / 20.0
        ),
        "likelihood_to_betray": min(
            1.0,
            ((10 - npc.trait_agreeableness) + npc.trait_neuroticism) / 20.0
        ),
        "likelihood_to_panic": min(
            1.0,
            npc.trait_neuroticism / 10.0
        ),
        "likelihood_to_negotiate": min(
            1.0,
            (npc.trait_openness + npc.trait_agreeableness) / 20.0
        ),
        "likelihood_to_forgive": min(
            1.0,
            (npc.trait_agreeableness + (10 - npc.trait_neuroticism)) / 20.0
        ),
    }