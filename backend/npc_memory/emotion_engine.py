import json
import random
from backend.database.db import SessionLocal, NPC, EmotionState
from backend.logger import get_logger

logger = get_logger("npc_memory.emotion")

# How much each action type affects emotion
ACTION_EMOTION_MAP = {
    # Player positive actions
    "player_helped": {
        "emotion": EmotionState.GRATEFUL,
        "intensity_delta": 0.4,
        "relationship_delta": 0.25,
    },
    "player_gave_gift": {
        "emotion": EmotionState.HAPPY,
        "intensity_delta": 0.3,
        "relationship_delta": 0.2,
    },
    "player_complimented": {
        "emotion": EmotionState.HAPPY,
        "intensity_delta": 0.15,
        "relationship_delta": 0.1,
    },
    "player_shared_info": {
        "emotion": EmotionState.GRATEFUL,
        "intensity_delta": 0.2,
        "relationship_delta": 0.15,
    },
    "player_defended": {
        "emotion": EmotionState.GRATEFUL,
        "intensity_delta": 0.5,
        "relationship_delta": 0.35,
    },

    # Player negative actions
    "player_attacked": {
        "emotion": EmotionState.HOSTILE,
        "intensity_delta": 0.8,
        "relationship_delta": -0.7,
    },
    "player_stole": {
        "emotion": EmotionState.ANGRY,
        "intensity_delta": 0.5,
        "relationship_delta": -0.5,
    },
    "player_lied": {
        "emotion": EmotionState.SUSPICIOUS,
        "intensity_delta": 0.35,
        "relationship_delta": -0.3,
    },
    "player_threatened": {
        "emotion": EmotionState.FEARFUL,
        "intensity_delta": 0.6,
        "relationship_delta": -0.4,
    },
    "player_insulted": {
        "emotion": EmotionState.ANGRY,
        "intensity_delta": 0.3,
        "relationship_delta": -0.25,
    },
    "player_betrayed": {
        "emotion": EmotionState.HOSTILE,
        "intensity_delta": 0.9,
        "relationship_delta": -0.8,
    },

    # Neutral/ambiguous actions
    "player_questioned": {
        "emotion": EmotionState.SUSPICIOUS,
        "intensity_delta": 0.1,
        "relationship_delta": 0.0,
    },
    "player_traded": {
        "emotion": EmotionState.NEUTRAL,
        "intensity_delta": 0.05,
        "relationship_delta": 0.05,
    },

    # World events
    "war_declared": {
        "emotion": EmotionState.FEARFUL,
        "intensity_delta": 0.4,
        "relationship_delta": 0.0,
    },
    "peace_treaty": {
        "emotion": EmotionState.HAPPY,
        "intensity_delta": 0.3,
        "relationship_delta": 0.0,
    },
    "disaster": {
        "emotion": EmotionState.FEARFUL,
        "intensity_delta": 0.5,
        "relationship_delta": 0.0,
    },
    "celebration": {
        "emotion": EmotionState.EXCITED,
        "intensity_delta": 0.3,
        "relationship_delta": 0.0,
    },
}

# How personality traits modify emotional response
# High neuroticism = amplifies all emotional changes
# Low neuroticism = dampens emotional changes
def get_personality_modifier(npc_neuroticism: float) -> float:
    """
    Returns emotion intensity multiplier based on neuroticism.
    neuroticism 1-10: 1=very stable, 10=very volatile
    """
    # Normalize to 0.5x - 2.0x multiplier
    return 0.5 + (npc_neuroticism / 10.0) * 1.5


def update_npc_emotion(
    npc_id: int,
    action_type: str,
    custom_intensity: float = None,
) -> dict:
    """
    Updates NPC emotion based on what just happened.

    Returns the new emotion state.
    """
    db = SessionLocal()
    try:
        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        if not npc:
            return {}

        # Get action config
        action_config = ACTION_EMOTION_MAP.get(action_type, {})
        if not action_config:
            logger.debug(f"Unknown action type: {action_type}")
            return {
                "emotion": npc.emotion_state,
                "intensity": npc.emotion_intensity,
            }

        new_emotion = action_config["emotion"]
        base_intensity_delta = action_config.get("intensity_delta", 0.2)

        # Apply personality modifier
        personality_mod = get_personality_modifier(
            npc.trait_neuroticism
        )
        intensity_delta = base_intensity_delta * personality_mod

        # Apply custom intensity override
        if custom_intensity is not None:
            intensity_delta = custom_intensity

        # Update emotion
        new_intensity = min(
            1.0,
            npc.emotion_intensity + intensity_delta
        )

        npc.emotion_state = new_emotion
        npc.emotion_intensity = new_intensity
        db.commit()

        logger.debug(
            f"Emotion updated | npc='{npc.name}' | "
            f"action={action_type} | "
            f"emotion={new_emotion} | intensity={new_intensity:.2f}"
        )

        return {
            "npc_id": npc_id,
            "npc_name": npc.name,
            "emotion": new_emotion,
            "intensity": round(new_intensity, 2),
            "action_that_caused": action_type,
        }

    finally:
        db.close()


def decay_emotions(world_id: int, days_passed: float = 1.0):
    """
    Gradually fades NPC emotions over time.
    Strong emotions fade slowly, weak emotions fade fast.

    Called by the world tick to simulate time passing.
    """
    db = SessionLocal()
    try:
        npcs = db.query(NPC).filter(
            NPC.world_id == world_id,
            NPC.is_alive == True,
            NPC.emotion_state != EmotionState.NEUTRAL,
        ).all()

        decayed_count = 0
        for npc in npcs:
            # Decay rate depends on emotion intensity
            # Strong emotions (intensity > 0.7) fade slowly
            # Weak emotions (intensity < 0.3) fade quickly
            if npc.emotion_intensity > 0.7:
                decay_rate = 0.05 * days_passed
            elif npc.emotion_intensity > 0.4:
                decay_rate = 0.1 * days_passed
            else:
                decay_rate = 0.2 * days_passed

            # High agreeableness = faster emotion decay
            # (more forgiving, moves on quicker)
            agreeableness_mod = npc.trait_agreeableness / 10.0
            decay_rate *= (0.5 + agreeableness_mod)

            new_intensity = max(
                0.0,
                npc.emotion_intensity - decay_rate
            )

            # Return to neutral if intensity drops too low
            if new_intensity < 0.15:
                npc.emotion_state = EmotionState.NEUTRAL
                npc.emotion_intensity = 0.3
            else:
                npc.emotion_intensity = new_intensity

            decayed_count += 1

        db.commit()
        logger.debug(
            f"Emotions decayed | world_id={world_id} | "
            f"npcs_affected={decayed_count}"
        )

    finally:
        db.close()


def get_emotion_description(
    emotion: str,
    intensity: float,
    npc_extraversion: float = 5.0,
) -> str:
    """
    Returns a human-readable description of the current emotion.
    High extraversion = emotion is more visible/expressed.
    """
    descriptions = {
        "happy": {
            "high": "beaming with joy",
            "medium": "in good spirits",
            "low": "seems slightly pleased",
        },
        "grateful": {
            "high": "deeply grateful, eyes showing appreciation",
            "medium": "genuinely thankful",
            "low": "mildly appreciative",
        },
        "angry": {
            "high": "furious, jaw clenched",
            "medium": "clearly irritated",
            "low": "slightly annoyed",
        },
        "fearful": {
            "high": "visibly terrified, hands trembling",
            "medium": "clearly nervous and on edge",
            "low": "slightly uneasy",
        },
        "suspicious": {
            "high": "eyes narrowed, watching your every move",
            "medium": "guarded and watchful",
            "low": "giving you careful looks",
        },
        "hostile": {
            "high": "barely containing rage, hand on weapon",
            "medium": "cold and confrontational",
            "low": "unfriendly and dismissive",
        },
        "sad": {
            "high": "visibly grief-stricken",
            "medium": "melancholy and withdrawn",
            "low": "looking a bit downcast",
        },
        "excited": {
            "high": "practically vibrating with excitement",
            "medium": "animated and enthusiastic",
            "low": "noticeably eager",
        },
        "neutral": {
            "high": "composed and professional",
            "medium": "neutral in expression",
            "low": "hard to read",
        },
    }

    # Determine intensity label
    if intensity >= 0.7:
        level = "high"
    elif intensity >= 0.4:
        level = "medium"
    else:
        level = "low"

    emotion_desc = descriptions.get(
        emotion, descriptions["neutral"]
    ).get(level, "neutral in expression")

    # Low extraversion = emotion less visible
    if npc_extraversion < 3.0:
        emotion_desc = f"subtly {emotion_desc}"

    return emotion_desc