import json
from backend.llm_client import chat_completion
from backend.npc_memory.memory_store import (
    retrieve_relevant_memories,
    store_memory,
    get_memory_count,
)
from backend.npc_memory.emotion_engine import (
    update_npc_emotion,
    get_emotion_description,
    ACTION_EMOTION_MAP,
)
from backend.npc_memory.relationship_engine import (
    get_npc_relationship_with_player,
    update_relationship_score,
    get_npc_behavior_from_relationship,
    get_relationship_info,
)
from backend.npc_memory.personality_engine import (
    get_personality_profile,
)
from backend.database.db import SessionLocal, NPC, Player
from backend.database.world_store import (
    get_location, record_event, get_world,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.procedural.world_context import build_world_context_string
from backend.logger import get_logger

logger = get_logger("npc_memory.dialogue")


def generate_npc_dialogue(
    npc_id: int,
    player_id: int,
    player_message: str,
    action_type: str = "player_questioned",
    world_id: int = None,
) -> dict:
    """
    The heart of Stage 3. Generates NPC dialogue with:

    1. Personality-driven voice and style
    2. Relevant memories retrieved from ChromaDB
    3. Current emotion state affecting tone
    4. Relationship score determining what is shared
    5. World context for consistency

    This makes every NPC conversation feel like talking
    to a real person with history and feelings.
    """
    logger.info(
        f"Generating dialogue | npc_id={npc_id} | "
        f"player_id={player_id} | action={action_type}"
    )

    # Load NPC data
    db = SessionLocal()
    try:
        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        player = db.query(Player).filter(Player.id == player_id).first()

        if not npc or not player:
            return {"error": "NPC or player not found"}

        npc_name = npc.name
        npc_role = npc.role
        player_name = player.character_name
        location_id = npc.location_id
        npc_world_id = world_id or npc.world_id

        # Snapshot key values before closing session
        npc_emotion = npc.emotion_state
        npc_emotion_intensity = npc.emotion_intensity
        npc_extraversion = npc.trait_extraversion
        npc_agreeableness = npc.trait_agreeableness
        npc_known_rumors = json.loads(npc.known_rumors or "[]")
        npc_known_secrets = json.loads(npc.known_secrets or "[]")
        npc_backstory = npc.backstory

    finally:
        db.close()

    # Get relationship info
    relationship = get_npc_relationship_with_player(
        npc_id, player_id
    )
    rel_score = relationship.get("relationship_score", 0.0)
    rel_info = get_relationship_info(rel_score)
    behaviors = get_npc_behavior_from_relationship(
        rel_score, npc_agreeableness
    )

    # Check if NPC will even talk
    if not behaviors["will_talk"]:
        hostile_responses = [
            f"{npc_name} turns away from you, refusing to acknowledge your presence.",
            f"'{npc_name} glares at you. 'Get away from me,' they snarl.",
            f"{npc_name} reaches for their weapon. 'I said stay away.'",
        ]
        import random
        response = random.choice(hostile_responses)
        return {
            "npc_id": npc_id,
            "npc_name": npc_name,
            "player_id": player_id,
            "response": response,
            "relationship": rel_info,
            "refused_to_talk": True,
        }

    # Retrieve relevant memories
    memories = retrieve_relevant_memories(
        npc_id=npc_id,
        query=player_message,
        player_id=player_id,
        n_results=5,
        min_importance=2,
    )

    # Get personality profile
    personality = get_personality_profile(npc_id)

    # Get world context
    world_context = ""
    world_time = {}
    if npc_world_id:
        world_context = build_world_context_string(npc_world_id)
        world_time = get_current_world_time(npc_world_id)

    # Get location context
    location = get_location(location_id) if location_id else None
    location_name = location.name if location else "Unknown location"

    # Build memory context string
    memory_context = ""
    if memories:
        memory_lines = []
        for mem in memories[:4]:
            days_ago = (
                world_time.get("total_days", 0) - mem["world_day"]
            )
            time_ref = (
                f"{int(days_ago)} days ago" if days_ago > 0
                else "recently"
            )
            memory_lines.append(
                f"- [{time_ref}] {mem['text']} "
                f"(felt {mem['emotion_at_time']} about this)"
            )
        memory_context = (
            f"\nYour memories of {player_name}:\n" +
            "\n".join(memory_lines)
        )
    else:
        memory_context = (
            f"\nYou have no memories of {player_name}. "
            f"This is the first time you've met."
        )

    # Build emotion description
    emotion_desc = get_emotion_description(
        npc_emotion,
        npc_emotion_intensity,
        npc_extraversion,
    )

    # Build what NPC will share based on relationship
    sharing_context = []
    if behaviors["shares_rumors"] and npc_known_rumors:
        sharing_context.append(
            f"You may share rumors if relevant: "
            f"{npc_known_rumors[0] if npc_known_rumors else ''}"
        )
    if behaviors["shares_secrets"] and npc_known_secrets:
        sharing_context.append(
            f"You may reveal a secret if the moment feels right: "
            f"{npc_known_secrets[0] if npc_known_secrets else ''}"
        )
    if behaviors["gives_discount"]:
        sharing_context.append(
            "You would offer this person a discount or favor."
        )

    sharing_str = "\n".join(sharing_context)

    # Build the complete prompt
    system_prompt = f"""You are {npc_name}, a {npc_role} in a dark fantasy RPG world.

YOUR IDENTITY:
{npc_backstory}

YOUR CURRENT STATE:
- You are in {location_name}
- You are currently {emotion_desc}
- Time: {world_time.get('time_string', 'unknown time')}

YOUR RELATIONSHIP WITH {player_name.upper()}:
- Relationship: {rel_info['label']} ({rel_info['description']})
- Relationship score: {rel_score:.2f} (-1.0 hostile to 1.0 devoted)
{memory_context}

YOUR PERSONALITY:
{personality.get('personality_summary', '')}

HOW YOU SPEAK:
{personality.get('dialogue_instructions', '')}

WHAT YOU CAN SHARE:
{sharing_str if sharing_str else 'Be guarded with information.'}

WORLD CONTEXT:
{world_context[:500] if world_context else 'Standard fantasy world.'}

RULES:
1. Stay completely in character as {npc_name}
2. Reference specific memories when relevant — show you remember
3. Let your current emotion color your words
4. Your relationship with {player_name} should be OBVIOUS in your tone
5. Never break the fourth wall
6. Speak in first person
7. Keep response to 2-4 sentences unless the situation demands more
8. End with something that invites player response or action"""

    user_prompt = f"""{player_name} says to you: "{player_message}"

Respond as {npc_name}:"""

    # Generate response
    response_text = chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=400,
        temperature=0.8,
    )

    # Update emotion based on action
    action_config = ACTION_EMOTION_MAP.get(action_type, {})
    rel_delta = action_config.get("relationship_delta", 0.0)

    emotion_update = update_npc_emotion(npc_id, action_type)
    rel_update = update_relationship_score(
        npc_id, player_id, rel_delta, reason=action_type
    )

    # Store this interaction as a memory
    memory_text = (
        f"{player_name} said: '{player_message[:100]}'. "
        f"I responded. Action type: {action_type}. "
        f"Relationship delta: {rel_delta:+.2f}."
    )

    store_memory(
        npc_id=npc_id,
        memory_text=memory_text,
        player_id=player_id,
        event_type=action_type,
        emotion_at_time=emotion_update.get(
            "emotion", "neutral"
        ),
        relationship_delta=rel_delta,
        world_day=world_time.get("total_days", 0.0),
        importance=_calculate_memory_importance(
            action_type, rel_delta
        ),
    )

    # Record world event for significant interactions
    if abs(rel_delta) >= 0.3 and npc_world_id:
        record_event(
            world_id=npc_world_id,
            event_type="dialogue",
            title=f"{player_name} and {npc_name}",
            description=(
                f"{player_name} had a significant interaction with "
                f"{npc_name} that {('strengthened' if rel_delta > 0 else 'damaged')} "
                f"their relationship."
            ),
            world_day=world_time.get("total_days", 0.0),
            location_id=location_id,
            player_id=player_id,
            npc_id=npc_id,
            importance=max(1, int(abs(rel_delta) * 10)),
        )

    logger.info(
        f"Dialogue generated | npc='{npc_name}' | "
        f"memories_used={len(memories)} | "
        f"rel_delta={rel_delta:+.2f} | "
        f"new_emotion={emotion_update.get('emotion')}"
    )

    return {
        "npc_id": npc_id,
        "npc_name": npc_name,
        "player_id": player_id,
        "response": response_text,
        "memories_used": len(memories),
        "emotion": {
            "state": emotion_update.get("emotion"),
            "intensity": emotion_update.get("intensity"),
            "description": emotion_desc,
        },
        "relationship": {
            "score": rel_update.get("new_score", rel_score) if rel_update else rel_score,
            "label": rel_update.get("new_label", rel_info["label"]) if rel_update else rel_info["label"],
            "tier_changed": rel_update.get("tier_changed", False) if rel_update else False,
        },
        "behaviors_unlocked": behaviors,
        "refused_to_talk": False,
    }


def _calculate_memory_importance(
    action_type: str,
    rel_delta: float,
) -> int:
    """
    Determines how important a memory is (1-10).
    Important memories are retrieved more often and decay slower.
    """
    base = 3

    # High relationship changes = important memory
    importance = base + int(abs(rel_delta) * 10)

    # Certain action types are always important
    high_importance_actions = [
        "player_attacked", "player_betrayed",
        "player_defended", "player_helped",
    ]
    if action_type in high_importance_actions:
        importance += 3

    return min(10, importance)