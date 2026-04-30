"""
Main quest generation pipeline.
Orchestrates quest personalization, generation, and database storage.
"""
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from backend.database.db import SessionLocal, Quest, QuestState, Player
from backend.database.world_store import (
    get_player, record_event, get_npc,
)
from backend.world_engine.world_clock import get_current_world_time
from backend.quest_generator.quest_personalizer import (
    select_quest_type_for_player,
    select_quest_difficulty,
    select_quest_giver,
    build_quest_context,
)
from backend.quest_generator.quest_builder import (
    generate_quest_content,
    generate_quest_chain,
)
from backend.quest_generator.quest_template import (
    QuestType, QuestDifficulty,
)
from backend.npc_memory.memory_store import store_memory
from backend.logger import get_logger

logger = get_logger("quest_generator.pipeline")


def generate_personalized_quest(
    player_id: int,
    world_id: int,
    location_id: int,
    quest_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    assign_to_npc: bool = True,
) -> Dict:
    """
    Generates a complete personalized quest for a player.
    
    This is the main entry point for quest generation.
    
    Args:
        player_id: Player ID
        world_id: World ID
        location_id: Starting location
        quest_type: Optional quest type to force
        difficulty: Optional difficulty to force
        assign_to_npc: Whether to assign quest to an NPC
        
    Returns:
        Complete quest dictionary with database ID
    """
    logger.info(
        f"Generating quest | player={player_id} | "
        f"world={world_id} | location={location_id}"
    )
    
    try:
        # Step 1: Select quest type and difficulty
        selected_type = select_quest_type_for_player(
            player_id, world_id, quest_type
        )
        selected_difficulty = select_quest_difficulty(
            player_id, world_id, difficulty
        )
        
        # Step 2: Build context
        context = build_quest_context(
            world_id, player_id, location_id,
            selected_type, selected_difficulty
        )
        
        # Step 3: Generate quest content with LLM
        quest_data = generate_quest_content(
            context, selected_type, selected_difficulty
        )
        
        # Step 4: Select quest giver NPC
        quest_giver_id = None
        if assign_to_npc:
            quest_giver_id = select_quest_giver(
                world_id, location_id, selected_type, player_id
            )
        
        # Step 5: Save to database
        quest_id = _save_quest_to_database(
            world_id=world_id,
            location_id=location_id,
            quest_giver_id=quest_giver_id,
            quest_data=quest_data,
            player_id=player_id,
        )
        
        quest_data["id"] = quest_id
        
        # Step 6: Store memory in quest giver NPC
        if quest_giver_id:
            _store_quest_giver_memory(
                quest_giver_id, player_id, quest_data, world_id
            )
        
        # Step 7: Record world event
        world_time = get_current_world_time(world_id)
        record_event(
            world_id=world_id,
            event_type="quest_update",
            title=f"New Quest Available: {quest_data['title']}",
            description=f"A new quest has become available at {context['location']['name']}",
            world_day=world_time.get("total_days", 0.0),
            location_id=location_id,
            player_id=player_id,
            is_notable=False,
            importance=2,
        )
        
        logger.info(
            f"Quest generated | id={quest_id} | "
            f"title='{quest_data['title']}' | type={selected_type.value}"
        )
        
        return quest_data
    
    except Exception as e:
        logger.error(f"Quest generation failed: {e}", exc_info=True)
        raise


def generate_quest_chain_for_player(
    player_id: int,
    world_id: int,
    location_id: int,
    chain_length: int = 3,
    starting_quest_type: Optional[str] = None,
) -> List[Dict]:
    """
    Generates a complete quest chain for a player.
    
    Args:
        player_id: Player ID
        world_id: World ID
        location_id: Starting location
        chain_length: Number of quests (2-5)
        starting_quest_type: Optional starting quest type
        
    Returns:
        List of quest dictionaries
    """
    logger.info(
        f"Generating quest chain | player={player_id} | "
        f"length={chain_length}"
    )
    
    try:
        # Select difficulty
        difficulty = select_quest_difficulty(player_id, world_id)
        
        # Build context
        context = build_quest_context(
            world_id, player_id, location_id,
            QuestType.FETCH,  # Placeholder
            difficulty
        )
        
        # Generate chain
        starting_type = None
        if starting_quest_type:
            starting_type = QuestType(starting_quest_type)
        
        quest_chain = generate_quest_chain(
            context, chain_length, starting_type
        )
        
        # Save each quest
        chain_id = f"chain_{uuid.uuid4().hex[:8]}"
        saved_quests = []
        
        for i, quest_data in enumerate(quest_chain):
            quest_data["chain_id"] = chain_id
            quest_data["chain_position"] = i + 1
            quest_data["chain_length"] = len(quest_chain)
            
            # First quest gets a quest giver
            quest_giver_id = None
            if i == 0:
                quest_type = QuestType(quest_data.get("quest_type", "fetch"))
                quest_giver_id = select_quest_giver(
                    world_id, location_id, quest_type, player_id
                )
            
            # Save to database
            quest_id = _save_quest_to_database(
                world_id=world_id,
                location_id=location_id,
                quest_giver_id=quest_giver_id,
                quest_data=quest_data,
                player_id=player_id,
            )
            
            quest_data["id"] = quest_id
            saved_quests.append(quest_data)
            
            # Store memory in quest giver for first quest
            if i == 0 and quest_giver_id:
                _store_quest_giver_memory(
                    quest_giver_id, player_id, quest_data, world_id
                )
        
        # Record chain creation event
        world_time = get_current_world_time(world_id)
        record_event(
            world_id=world_id,
            event_type="quest_update",
            title=f"Quest Chain Available: {saved_quests[0]['title']}",
            description=f"A {chain_length}-part quest chain has begun",
            world_day=world_time.get("total_days", 0.0),
            location_id=location_id,
            player_id=player_id,
            is_notable=True,
            importance=5,
        )
        
        logger.info(
            f"Quest chain generated | chain_id={chain_id} | "
            f"quests={len(saved_quests)}"
        )
        
        return saved_quests
    
    except Exception as e:
        logger.error(f"Quest chain generation failed: {e}", exc_info=True)
        raise


def _save_quest_to_database(
    world_id: int,
    location_id: int,
    quest_giver_id: Optional[int],
    quest_data: Dict,
    player_id: Optional[int] = None,
) -> int:
    """
    Saves a quest to the database.
    
    Args:
        world_id: World ID
        location_id: Origin location
        quest_giver_id: NPC giving the quest
        quest_data: Quest dictionary
        player_id: Optional player to assign quest to
        
    Returns:
        Quest ID
    """
    db = SessionLocal()
    try:
        # Calculate expiry
        world_time = get_current_world_time(world_id)
        current_day = world_time.get("total_days", 0.0)
        
        expires_at = None
        if quest_data.get("has_time_pressure"):
            expires_in = quest_data.get("expires_in_days", 7.0)
            expires_at = current_day + expires_in
        
        # Create quest
        quest = Quest(
            world_id=world_id,
            origin_location_id=location_id,
            given_by_npc_id=quest_giver_id,
            title=quest_data.get("title", "Untitled Quest"),
            description=quest_data.get("description", ""),
            quest_type=quest_data.get("quest_type", "fetch"),
            state=QuestState.AVAILABLE,
            trigger_conditions=json.dumps(
                quest_data.get("trigger_conditions", {})
            ),
            objectives=json.dumps(quest_data.get("objectives", [])),
            rewards=json.dumps(quest_data.get("rewards", {})),
            assigned_player_id=player_id,
            expires_at_world_day=expires_at,
            created_at_world_day=current_day,
        )
        
        db.add(quest)
        db.commit()
        db.refresh(quest)
        
        quest_id = quest.id
        
        # Update player's quest log if assigned
        if player_id:
            player = db.query(Player).filter(Player.id == player_id).first()
            if player:
                quest_log = json.loads(player.quest_log or "{}")
                quest_log[str(quest_id)] = {
                    "state": "available",
                    "type": quest_data.get("quest_type"),
                    "title": quest_data.get("title"),
                    "added_at": datetime.utcnow().isoformat(),
                }
                player.quest_log = json.dumps(quest_log)
                db.commit()
        
        return quest_id
    
    finally:
        db.close()


def _store_quest_giver_memory(
    npc_id: int,
    player_id: int,
    quest_data: Dict,
    world_id: int,
):
    """
    Stores a memory in the quest giver NPC about offering this quest.
    
    Args:
        npc_id: NPC ID
        player_id: Player ID
        quest_data: Quest data
        world_id: World ID
    """
    try:
        npc = get_npc(npc_id)
        if not npc:
            return
        
        world_time = get_current_world_time(world_id)
        
        memory_text = (
            f"I offered {quest_data['title']} to a traveler. "
            f"The quest involves: {quest_data['description']}"
        )
        
        store_memory(
            npc_id=npc_id,
            memory_text=memory_text,
            player_id=player_id,
            event_type="quest_offered",
            importance=6,
            world_day=world_time.get("total_days", 0.0),
        )
        
        logger.debug(f"Quest memory stored | npc={npc_id} | quest={quest_data['title']}")
    
    except Exception as e:
        logger.warning(f"Failed to store quest giver memory: {e}")


def get_active_quests_for_player(player_id: int, world_id: int) -> List[Dict]:
    """
    Gets all active quests for a player.
    
    Args:
        player_id: Player ID
        world_id: World ID
        
    Returns:
        List of active quest dictionaries
    """
    db = SessionLocal()
    try:
        quests = db.query(Quest).filter(
            Quest.world_id == world_id,
            Quest.assigned_player_id == player_id,
            Quest.state.in_([QuestState.ACTIVE, QuestState.AVAILABLE])
        ).all()
        
        result = []
        for quest in quests:
            result.append({
                "id": quest.id,
                "title": quest.title,
                "description": quest.description,
                "type": quest.quest_type,
                "state": quest.state,
                "objectives": json.loads(quest.objectives or "[]"),
                "rewards": json.loads(quest.rewards or "{}"),
                "expires_at": quest.expires_at_world_day,
            })
        
        return result
    
    finally:
        db.close()


def complete_quest(
    quest_id: int,
    player_id: int,
    world_id: int,
    completion_method: str = "standard",
) -> Dict:
    """
    Marks a quest as completed and grants rewards.
    
    Args:
        quest_id: Quest ID
        player_id: Player ID
        world_id: World ID
        completion_method: How it was completed (combat, stealth, diplomatic, etc.)
        
    Returns:
        Completion result with rewards granted
    """
    logger.info(
        f"Completing quest | quest={quest_id} | "
        f"player={player_id} | method={completion_method}"
    )
    
    db = SessionLocal()
    try:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        if not quest:
            raise ValueError(f"Quest {quest_id} not found")
        
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player:
            raise ValueError(f"Player {player_id} not found")
        
        # Update quest state
        quest.state = QuestState.COMPLETED
        quest.completed_at = datetime.utcnow()
        
        # Grant rewards
        rewards = json.loads(quest.rewards or "{}")
        
        gold_reward = rewards.get("gold", 0)
        xp_reward = rewards.get("experience", 0)
        
        player.gold += gold_reward
        player.experience += xp_reward
        
        # Update faction reputation
        reputation_changes = rewards.get("reputation_changes", {})
        if reputation_changes:
            player_reputation = json.loads(player.faction_reputation or "{}")
            for faction_id, change in reputation_changes.items():
                current = player_reputation.get(str(faction_id), 0)
                player_reputation[str(faction_id)] = current + change
            player.faction_reputation = json.dumps(player_reputation)
        
        # Update quest log
        quest_log = json.loads(player.quest_log or "{}")
        quest_log[str(quest_id)] = {
            "state": "completed",
            "type": quest.quest_type,
            "title": quest.title,
            "completed_at": datetime.utcnow().isoformat(),
            "completion_method": completion_method,
        }
        player.quest_log = json.dumps(quest_log)
        
        db.commit()
        
        # Record completion event
        world_time = get_current_world_time(world_id)
        record_event(
            world_id=world_id,
            event_type="quest_update",
            title=f"Quest Completed: {quest.title}",
            description=f"{player.character_name} completed {quest.title}",
            world_day=world_time.get("total_days", 0.0),
            location_id=quest.origin_location_id,
            player_id=player_id,
            is_notable=True,
            importance=4,
        )
        
        # Store memory in quest giver
        if quest.given_by_npc_id:
            memory_text = (
                f"{player.character_name} completed the quest I gave them: "
                f"{quest.title}. They succeeded using {completion_method} approach."
            )
            store_memory(
                npc_id=quest.given_by_npc_id,
                memory_text=memory_text,
                player_id=player_id,
                event_type="quest_completed",
                importance=7,
                world_day=world_time.get("total_days", 0.0),
            )
        
        logger.info(
            f"Quest completed | quest={quest_id} | "
            f"gold={gold_reward} | xp={xp_reward}"
        )
        
        return {
            "quest_id": quest_id,
            "quest_title": quest.title,
            "rewards_granted": {
                "gold": gold_reward,
                "experience": xp_reward,
                "reputation_changes": reputation_changes,
            },
            "completion_method": completion_method,
        }
    
    finally:
        db.close()


def fail_quest(quest_id: int, player_id: int, world_id: int, reason: str = "abandoned") -> Dict:
    """
    Marks a quest as failed.
    
    Args:
        quest_id: Quest ID
        player_id: Player ID
        world_id: World ID
        reason: Failure reason
        
    Returns:
        Failure result
    """
    logger.info(f"Failing quest | quest={quest_id} | reason={reason}")
    
    db = SessionLocal()
    try:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        if not quest:
            raise ValueError(f"Quest {quest_id} not found")
        
        quest.state = QuestState.FAILED
        
        # Update player quest log
        player = db.query(Player).filter(Player.id == player_id).first()
        if player:
            quest_log = json.loads(player.quest_log or "{}")
            quest_log[str(quest_id)] = {
                "state": "failed",
                "type": quest.quest_type,
                "title": quest.title,
                "failed_at": datetime.utcnow().isoformat(),
                "reason": reason,
            }
            player.quest_log = json.dumps(quest_log)
        
        db.commit()
        
        return {
            "quest_id": quest_id,
            "quest_title": quest.title,
            "failed": True,
            "reason": reason,
        }
    
    finally:
        db.close()
