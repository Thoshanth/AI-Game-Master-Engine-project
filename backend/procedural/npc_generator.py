import json
import random
from backend.llm_client import chat_completion_json
from backend.procedural.world_context import build_npc_generation_context
from backend.procedural.name_generator import generate_npc_name
from backend.database.world_store import (
    create_npc, get_location, get_factions,
    record_event, get_world,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.logger import get_logger

logger = get_logger("procedural.npc")

# Role → personality tendencies
ROLE_PERSONALITY_HINTS = {
    "merchant": "business-minded, calculating, friendly to customers",
    "guard": "dutiful, suspicious of strangers, loyal to employer",
    "innkeeper": "hospitable, gossip-lover, seen everything",
    "blacksmith": "hard-working, proud of craft, straightforward",
    "mage": "intellectual, secretive, obsessed with knowledge",
    "priest": "devout, compassionate, but possibly hiding doubts",
    "thief": "cunning, distrustful, opportunistic",
    "noble": "arrogant, political, hiding family secrets",
    "peasant": "hardworking, superstitious, struggling to survive",
    "warrior": "battle-hardened, direct, haunted by past violence",
    "quest_giver": "desperate, hiding something, needs help urgently",
    "villain": "intelligent, believes in their own righteousness",
    "companion": "loyal, with their own agenda and personal goals",
}


def generate_npc_with_context(
    world_id: int,
    location_id: int,
    role: str,
    faction_id: int = None,
    player_context: dict = None,
) -> dict:
    """
    Generates an NPC that is deeply connected to the world state.

    The NPC will:
    - Know relevant world events and rumors
    - Have opinions shaped by faction politics
    - React appropriately to player reputation
    - Have secrets connected to current world events
    - Behave consistently with their role and location
    """
    logger.info(
        f"Generating NPC | role={role} | "
        f"location_id={location_id}"
    )

    location = get_location(location_id)
    if not location:
        raise ValueError(f"Location {location_id} not found")

    factions = get_factions(world_id)
    faction = next(
        (f for f in factions if f.id == faction_id), None
    )

    npc_context = build_npc_generation_context(
        world_id=world_id,
        location_name=location.name,
        location_type=location.location_type,
        faction_name=faction.name if faction else None,
        player_reputation=player_context,
    )

    personality_hint = ROLE_PERSONALITY_HINTS.get(
        role, "complex and layered personality"
    )

    # Determine gender
    gender = random.choice(["male", "female", "non-binary"])

    prompt = f"""{npc_context}

Create a deeply realized NPC for this RPG world.

Role: {role}
Personality tendency: {personality_hint}
Location type: {location.location_type}
Location safety level: {location.safety_level}/10
Location wealth level: {location.wealth_level}/10

This NPC must:
1. Feel like a real person shaped by this specific world
2. Know things relevant to the current world state
3. Have opinions about the active factions and events
4. Have personal goals connected to the world situation
5. Have at least one secret that could drive a quest

Return ONLY valid JSON:
{{
    "name": "Full name",
    "age": 20-80,
    "gender": "{gender}",
    "appearance": "3 sentences describing physical appearance and distinctive features",
    "backstory": "3-4 sentences of personal history shaped by world events",
    "personality": "2-3 sentences describing how they actually behave",
    "current_situation": "What is this NPC dealing with right now?",
    "goals": [
        "their primary personal goal",
        "a secondary goal"
    ],
    "fears": ["their main fear"],
    "secrets": [
        "a secret they are hiding that connects to world events"
    ],
    "opinion_of_factions": {{
        "faction_name": "their opinion"
    }},
    "known_rumors": [
        "a rumor they know about current events",
        "another piece of information they have"
    ],
    "dialogue_style": "How do they speak? Formal, gruff, nervous, cheerful?",
    "initial_attitude": "friendly|neutral|suspicious|hostile",
    "quest_hook": "What problem do they have that players could help with?",
    "traits": {{
        "openness": 1.0-10.0,
        "conscientiousness": 1.0-10.0,
        "extraversion": 1.0-10.0,
        "agreeableness": 1.0-10.0,
        "neuroticism": 1.0-10.0
    }}
}}

Return valid JSON only."""

    try:
        raw = chat_completion_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a creative character designer for an RPG. "
                        "Return valid JSON only."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
        )

        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        npc_data = json.loads(cleaned.strip())
        logger.info(
            f"NPC data generated | name='{npc_data.get('name')}'"
        )
        return npc_data

    except Exception as e:
        logger.error(f"NPC generation failed: {e}")
        return _default_npc_data(role, gender)


def create_procedural_npc(
    world_id: int,
    location_id: int,
    role: str,
    faction_id: int = None,
    player_context: dict = None,
) -> dict:
    """
    Generates and saves a complete NPC to the database.
    """
    npc_data = generate_npc_with_context(
        world_id=world_id,
        location_id=location_id,
        role=role,
        faction_id=faction_id,
        player_context=player_context,
    )

    # Save NPC to database
    npc = create_npc(
        world_id=world_id,
        location_id=location_id,
        name=npc_data.get(
            "name",
            generate_npc_name(npc_data.get("gender", "neutral"))
        ),
        role=role,
        appearance=npc_data.get("appearance", ""),
        backstory=npc_data.get("backstory", ""),
        age=npc_data.get("age", 30),
        gender=npc_data.get("gender", "neutral"),
        faction_id=faction_id,
        traits=npc_data.get("traits", {}),
    )

    # Store secrets, rumors, and goals
    from backend.database.db import SessionLocal, NPC as NPCModel
    db = SessionLocal()
    try:
        npc_record = db.query(NPCModel).filter(
            NPCModel.id == npc.id
        ).first()
        if npc_record:
            npc_record.known_secrets = json.dumps(
                npc_data.get("secrets", [])
            )
            npc_record.known_rumors = json.dumps(
                npc_data.get("known_rumors", [])
            )
            npc_record.known_facts = json.dumps(
                npc_data.get("goals", [])
            )
            db.commit()
    finally:
        db.close()

    # Record NPC arrival event
    world_time = get_current_world_time(world_id)
    record_event(
        world_id=world_id,
        event_type="npc_action",
        title=f"{npc.name} Appears",
        description=(
            f"A {role} named {npc.name} is now present "
            f"at location {location_id}."
        ),
        world_day=world_time.get("total_days", 0.0),
        location_id=location_id,
        npc_id=npc.id,
        importance=1,
    )

    location = get_location(location_id)

    logger.info(
        f"Procedural NPC created | "
        f"name='{npc.name}' | role={role} | id={npc.id}"
    )

    return {
        "id": npc.id,
        "name": npc.name,
        "age": npc_data.get("age", 30),
        "gender": npc_data.get("gender", "neutral"),
        "role": role,
        "location": location.name if location else "Unknown",
        "appearance": npc_data.get("appearance", ""),
        "backstory": npc_data.get("backstory", ""),
        "personality": npc_data.get("personality", ""),
        "current_situation": npc_data.get("current_situation", ""),
        "goals": npc_data.get("goals", []),
        "fears": npc_data.get("fears", []),
        "secrets": npc_data.get("secrets", []),
        "known_rumors": npc_data.get("known_rumors", []),
        "dialogue_style": npc_data.get("dialogue_style", ""),
        "initial_attitude": npc_data.get("initial_attitude", "neutral"),
        "quest_hook": npc_data.get("quest_hook", ""),
        "opinion_of_factions": npc_data.get("opinion_of_factions", {}),
    }


def _default_npc_data(role: str, gender: str) -> dict:
    """Fallback NPC data if LLM fails."""
    names_m = ["Aldric", "Bram", "Cael", "Dorn", "Edmund"]
    names_f = ["Alara", "Brynn", "Cora", "Delia", "Elara"]
    name = (
        random.choice(names_m)
        if gender == "male"
        else random.choice(names_f)
    )
    return {
        "name": name,
        "age": random.randint(25, 60),
        "gender": gender,
        "appearance": f"A weathered individual with tired eyes.",
        "backstory": f"Has worked as a {role} for many years.",
        "personality": "Reserved but helpful when trust is earned.",
        "current_situation": "Going about their daily work.",
        "goals": ["survive the current troubles"],
        "fears": ["the growing darkness in the world"],
        "secrets": ["knows something they shouldn't"],
        "known_rumors": ["strange things are happening nearby"],
        "dialogue_style": "Speaks carefully, choosing words with care.",
        "initial_attitude": "neutral",
        "quest_hook": "Has a problem that needs solving.",
        "traits": {
            "openness": 5.0,
            "conscientiousness": 6.0,
            "extraversion": 4.0,
            "agreeableness": 5.0,
            "neuroticism": 5.0,
        },
    }