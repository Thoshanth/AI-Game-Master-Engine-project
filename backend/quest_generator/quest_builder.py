"""
LLM-powered quest content generation.
Generates quest title, description, objectives, dialogue, and rewards.
"""
import json
from typing import Dict, List, Optional
from backend.llm_client import chat_completion_json
from backend.quest_generator.quest_template import (
    QuestType, QuestDifficulty,
    create_quest_template,
    get_difficulty_multipliers,
    validate_quest_structure,
)
from backend.logger import get_logger

logger = get_logger("quest_generator.builder")


def generate_quest_content(
    quest_context: Dict,
    quest_type: QuestType,
    difficulty: QuestDifficulty,
) -> Dict:
    """
    Uses LLM to generate complete quest content.
    
    Args:
        quest_context: World and player context
        quest_type: Type of quest
        difficulty: Difficulty level
        
    Returns:
        Complete quest dictionary
    """
    logger.info(
        f"Generating quest | type={quest_type.value} | "
        f"difficulty={difficulty.value}"
    )
    
    # Get base template
    template = create_quest_template(quest_type, difficulty)
    multipliers = get_difficulty_multipliers(difficulty)
    
    # Build LLM prompt
    prompt = _build_generation_prompt(
        quest_context, quest_type, difficulty, template
    )
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are a quest designer for an AI-powered RPG. "
                "Generate engaging, lore-consistent quests that fit "
                "the current world state and player profile. "
                "Return ONLY valid JSON with no markdown formatting."
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]
    
    try:
        response = chat_completion_json(messages, max_tokens=1500)
        
        # Parse JSON response
        quest_data = json.loads(response)
        
        # Merge with template
        complete_quest = {**template, **quest_data}
        
        # Validate structure
        if not validate_quest_structure(complete_quest):
            logger.error("Generated quest failed validation")
            return template
        
        logger.info(f"Quest generated | title='{complete_quest.get('title')}'")
        return complete_quest
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse quest JSON: {e}")
        logger.error(f"Response was: {response[:200]}")
        return template
    
    except Exception as e:
        logger.error(f"Quest generation failed: {e}", exc_info=True)
        return template


def _build_generation_prompt(
    context: Dict,
    quest_type: QuestType,
    difficulty: QuestDifficulty,
    template: Dict,
) -> str:
    """
    Builds the LLM prompt for quest generation.
    
    Args:
        context: Quest context
        quest_type: Type of quest
        difficulty: Difficulty level
        template: Base template
        
    Returns:
        Prompt string
    """
    player = context["player"]
    location = context["location"]
    recent_events = context["recent_events"]
    factions = context["relevant_factions"]
    
    events_text = "\n".join([
        f"- {e['title']}: {e['description']}"
        for e in recent_events[:3]
    ])
    
    factions_text = "\n".join([
        f"- {f['name']} ({f['type']}): reputation {f['reputation']}"
        for f in factions[:3]
    ]) if factions else "No faction relationships yet"
    
    prompt = f"""Generate a {quest_type.value} quest with {difficulty.value} difficulty.

PLAYER CONTEXT:
- Name: {player['name']}
- Class: {player['class']}
- Level: {player['level']}

LOCATION:
- Name: {location['name']}
- Type: {location['type']}
- Description: {location['description']}

RECENT WORLD EVENTS:
{events_text}

FACTION RELATIONSHIPS:
{factions_text}

QUEST TYPE: {quest_type.value}
DIFFICULTY: {difficulty.value}

Generate a quest that:
1. Fits the current world state and recent events
2. Is appropriate for the player's level and location
3. Has clear, achievable objectives
4. Includes engaging NPC dialogue for the quest giver
5. Offers rewards appropriate to difficulty
6. Connects to world lore and ongoing events

Return JSON with this structure:
{{
    "title": "Quest title (short, engaging)",
    "description": "Full quest description (2-3 sentences)",
    "quest_giver_dialogue": {{
        "introduction": "What the NPC says when offering the quest",
        "acceptance": "What they say when player accepts",
        "reminder": "What they say if player returns without completing",
        "completion": "What they say when quest is completed"
    }},
    "objectives": [
        "Objective 1 (specific and measurable)",
        "Objective 2",
        "Objective 3"
    ],
    "rewards": {{
        "gold": {template['rewards']['gold']},
        "experience": {template['rewards']['experience']},
        "reputation_changes": {{}},
        "special_reward": "Optional special item or unlock"
    }},
    "failure_consequences": "What happens if the quest fails or expires",
    "lore_connection": "How this quest connects to world events or history"
}}

Return ONLY the JSON object, no markdown formatting."""
    
    return prompt


def generate_quest_chain(
    quest_context: Dict,
    chain_length: int = 3,
    starting_quest_type: Optional[QuestType] = None,
) -> List[Dict]:
    """
    Generates a chain of connected quests.
    
    Each quest in the chain builds on the previous one,
    with escalating difficulty and stakes.
    
    Args:
        quest_context: World and player context
        chain_length: Number of quests in chain (2-5)
        starting_quest_type: Optional starting quest type
        
    Returns:
        List of quest dictionaries
    """
    logger.info(f"Generating quest chain | length={chain_length}")
    
    chain_length = max(2, min(5, chain_length))
    quests = []
    
    # Difficulty progression
    difficulty_progression = [
        QuestDifficulty.EASY,
        QuestDifficulty.MODERATE,
        QuestDifficulty.HARD,
        QuestDifficulty.VERY_HARD,
        QuestDifficulty.LEGENDARY,
    ]
    
    # Get starting difficulty from context
    base_difficulty = QuestDifficulty(quest_context.get("difficulty", "moderate"))
    start_index = difficulty_progression.index(base_difficulty)
    
    # Generate chain prompt
    prompt = _build_chain_prompt(
        quest_context, chain_length, starting_quest_type
    )
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are a quest designer creating connected quest chains. "
                "Each quest should build on the previous one with escalating "
                "stakes and difficulty. Return ONLY valid JSON."
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]
    
    try:
        response = chat_completion_json(messages, max_tokens=2500)
        chain_data = json.loads(response)
        
        # Process each quest in chain
        for i, quest_data in enumerate(chain_data.get("quests", [])[:chain_length]):
            # Assign progressive difficulty
            difficulty_index = min(
                start_index + i,
                len(difficulty_progression) - 1
            )
            difficulty = difficulty_progression[difficulty_index]
            
            # Create template and merge
            quest_type = QuestType(quest_data.get("quest_type", "fetch"))
            template = create_quest_template(quest_type, difficulty)
            
            complete_quest = {**template, **quest_data}
            complete_quest["chain_position"] = i + 1
            complete_quest["chain_length"] = chain_length
            complete_quest["unlocks_quest"] = i + 1 if i < chain_length - 1 else None
            
            quests.append(complete_quest)
        
        logger.info(f"Quest chain generated | quests={len(quests)}")
        return quests
    
    except Exception as e:
        logger.error(f"Quest chain generation failed: {e}", exc_info=True)
        return []


def _build_chain_prompt(
    context: Dict,
    chain_length: int,
    starting_quest_type: Optional[QuestType],
) -> str:
    """Builds prompt for quest chain generation."""
    
    player = context["player"]
    location = context["location"]
    
    type_hint = f"Start with a {starting_quest_type.value} quest." if starting_quest_type else ""
    
    prompt = f"""Generate a quest chain of {chain_length} connected quests.

PLAYER: {player['name']} (Level {player['level']} {player['class']})
STARTING LOCATION: {location['name']}

{type_hint}

The quest chain should:
1. Tell a cohesive story across all quests
2. Escalate in difficulty and stakes
3. Have each quest unlock the next
4. Build to a climactic final quest
5. Connect to world events and lore

Return JSON:
{{
    "chain_title": "Overall story arc title",
    "chain_description": "What this quest chain is about",
    "quests": [
        {{
            "title": "Quest 1 title",
            "description": "Quest 1 description",
            "quest_type": "fetch|deliver|kill|investigate|etc",
            "objectives": ["obj1", "obj2"],
            "quest_giver_dialogue": {{
                "introduction": "...",
                "acceptance": "...",
                "completion": "..."
            }},
            "rewards": {{"gold": 50, "experience": 100}},
            "lore_connection": "How this connects to the story"
        }},
        ... (repeat for {chain_length} quests)
    ]
}}

Return ONLY the JSON object."""
    
    return prompt


def add_quest_variants(base_quest: Dict, variant_count: int = 2) -> List[Dict]:
    """
    Creates variants of a quest with different approaches.
    
    For example, a rescue quest might have:
    - Stealth variant (sneak in)
    - Combat variant (fight through)
    - Diplomatic variant (negotiate)
    
    Args:
        base_quest: Base quest dictionary
        variant_count: Number of variants to create
        
    Returns:
        List of quest variants including the base
    """
    variants = [base_quest]
    
    # Variant approaches by quest type
    approach_variants = {
        QuestType.RESCUE: ["stealth", "combat", "diplomatic"],
        QuestType.INVESTIGATE: ["interrogation", "stealth", "research"],
        QuestType.FETCH: ["purchase", "steal", "trade"],
        QuestType.DIPLOMATIC: ["persuasion", "intimidation", "bribery"],
    }
    
    quest_type = QuestType(base_quest.get("quest_type", "fetch"))
    approaches = approach_variants.get(quest_type, [])
    
    if not approaches or variant_count < 2:
        return variants
    
    for approach in approaches[:variant_count - 1]:
        variant = base_quest.copy()
        variant["variant_approach"] = approach
        variant["title"] = f"{base_quest['title']} ({approach.title()})"
        
        # Modify objectives based on approach
        if approach == "stealth":
            variant["objectives"] = [
                obj.replace("Defeat", "Sneak past").replace("Fight", "Avoid")
                for obj in variant["objectives"]
            ]
        elif approach == "diplomatic":
            variant["objectives"] = [
                obj.replace("Defeat", "Negotiate with").replace("Kill", "Convince")
                for obj in variant["objectives"]
            ]
        
        variants.append(variant)
    
    return variants
