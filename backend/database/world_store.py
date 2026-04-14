import json
from datetime import datetime
from typing import Optional
from backend.database.db import (
    SessionLocal, World, Region, Location,
    NPC, Player, Faction, Quest, Item,
    WorldEvent, PlayerAction, FactionRelationship,
    QuestState, EventType,
)
from backend.logger import get_logger

logger = get_logger("database.world_store")


# ── World Operations ───────────────────────────────────────────────

def create_world(name: str, description: str, time_ratio: float = 3600.0) -> World:
    """Creates a new game world."""
    db = SessionLocal()
    try:
        world = World(
            name=name,
            description=description,
            time_ratio=time_ratio,
            global_state=json.dumps({
                "active_wars": [],
                "economic_state": "stable",
                "major_events": [],
                "current_season": "spring",
                "political_tensions": [],
            })
        )
        db.add(world)
        db.commit()
        db.refresh(world)
        logger.info(f"World created | id={world.id} | name='{name}'")
        return world
    finally:
        db.close()


def get_world(world_id: int) -> Optional[World]:
    db = SessionLocal()
    try:
        return db.query(World).filter(World.id == world_id).first()
    finally:
        db.close()


def get_world_by_name(name: str) -> Optional[World]:
    db = SessionLocal()
    try:
        return db.query(World).filter(World.name == name).first()
    finally:
        db.close()


def get_all_worlds() -> list[World]:
    db = SessionLocal()
    try:
        return db.query(World).all()
    finally:
        db.close()


def update_world_time(world_id: int, new_day: float, season: str):
    """Updates the world clock."""
    db = SessionLocal()
    try:
        world = db.query(World).filter(World.id == world_id).first()
        if world:
            world.world_time_days = new_day
            world.world_season = season
            db.commit()
    finally:
        db.close()


def update_global_state(world_id: int, updates: dict):
    """Updates the world's global state JSON."""
    db = SessionLocal()
    try:
        world = db.query(World).filter(World.id == world_id).first()
        if world:
            current = json.loads(world.global_state or "{}")
            current.update(updates)
            world.global_state = json.dumps(current)
            db.commit()
    finally:
        db.close()


# ── Region Operations ──────────────────────────────────────────────

def create_region(
    world_id: int,
    name: str,
    description: str,
    terrain_type: str,
    danger_level: int = 1,
    map_x: float = 50.0,
    map_y: float = 50.0,
    resources: list = None,
) -> Region:
    db = SessionLocal()
    try:
        region = Region(
            world_id=world_id,
            name=name,
            description=description,
            terrain_type=terrain_type,
            danger_level=danger_level,
            map_x=map_x,
            map_y=map_y,
            resources=json.dumps(resources or []),
        )
        db.add(region)
        db.commit()
        db.refresh(region)
        logger.info(
            f"Region created | id={region.id} | name='{name}' | "
            f"world_id={world_id}"
        )
        return region
    finally:
        db.close()


def get_regions(world_id: int) -> list[Region]:
    db = SessionLocal()
    try:
        return db.query(Region).filter(
            Region.world_id == world_id
        ).all()
    finally:
        db.close()


# ── Location Operations ────────────────────────────────────────────

def create_location(
    region_id: int,
    name: str,
    location_type: str,
    description: str,
    population: int = 0,
    wealth_level: int = 5,
    safety_level: int = 5,
    map_x: float = 50.0,
    map_y: float = 50.0,
    history: str = "",
) -> Location:
    db = SessionLocal()
    try:
        location = Location(
            region_id=region_id,
            name=name,
            location_type=location_type,
            description=description,
            population=population,
            wealth_level=wealth_level,
            safety_level=safety_level,
            map_x=map_x,
            map_y=map_y,
            history=history,
            current_events=json.dumps([]),
            rumors=json.dumps([]),
        )
        db.add(location)
        db.commit()
        db.refresh(location)
        logger.info(
            f"Location created | id={location.id} | "
            f"name='{name}' | type={location_type}"
        )
        return location
    finally:
        db.close()


def get_locations(region_id: int) -> list[Location]:
    db = SessionLocal()
    try:
        return db.query(Location).filter(
            Location.region_id == region_id
        ).all()
    finally:
        db.close()


def get_location(location_id: int) -> Optional[Location]:
    db = SessionLocal()
    try:
        return db.query(Location).filter(
            Location.id == location_id
        ).first()
    finally:
        db.close()


def add_rumor_to_location(location_id: int, rumor: str):
    """Adds a rumor to a location — NPCs will repeat these."""
    db = SessionLocal()
    try:
        location = db.query(Location).filter(
            Location.id == location_id
        ).first()
        if location:
            rumors = json.loads(location.rumors or "[]")
            rumors.append({
                "text": rumor,
                "added_at": datetime.utcnow().isoformat(),
            })
            # Keep only last 10 rumors
            rumors = rumors[-10:]
            location.rumors = json.dumps(rumors)
            db.commit()
    finally:
        db.close()


# ── NPC Operations ─────────────────────────────────────────────────

def create_npc(
    world_id: int,
    location_id: int,
    name: str,
    role: str,
    appearance: str,
    backstory: str,
    age: int = 30,
    gender: str = "neutral",
    faction_id: int = None,
    traits: dict = None,
) -> NPC:
    db = SessionLocal()
    try:
        t = traits or {}
        npc = NPC(
            world_id=world_id,
            location_id=location_id,
            faction_id=faction_id,
            name=name,
            age=age,
            gender=gender,
            role=role,
            appearance=appearance,
            backstory=backstory,
            trait_openness=t.get("openness", 5.0),
            trait_conscientiousness=t.get("conscientiousness", 5.0),
            trait_extraversion=t.get("extraversion", 5.0),
            trait_agreeableness=t.get("agreeableness", 5.0),
            trait_neuroticism=t.get("neuroticism", 5.0),
            relationships=json.dumps({}),
            known_facts=json.dumps([]),
            known_secrets=json.dumps([]),
            known_rumors=json.dumps([]),
            schedule=json.dumps({
                "6": "waking up",
                "8": "working",
                "12": "eating lunch",
                "14": "working",
                "18": "relaxing",
                "20": "at tavern",
                "22": "sleeping",
            }),
        )
        db.add(npc)
        db.commit()
        db.refresh(npc)
        logger.info(
            f"NPC created | id={npc.id} | name='{name}' | "
            f"role={role} | location_id={location_id}"
        )
        return npc
    finally:
        db.close()


def get_npcs_at_location(location_id: int) -> list[NPC]:
    db = SessionLocal()
    try:
        return db.query(NPC).filter(
            NPC.location_id == location_id,
            NPC.is_alive == True,
        ).all()
    finally:
        db.close()


def get_npc(npc_id: int) -> Optional[NPC]:
    db = SessionLocal()
    try:
        return db.query(NPC).filter(NPC.id == npc_id).first()
    finally:
        db.close()


def update_npc_emotion(
    npc_id: int,
    emotion: str,
    intensity: float,
):
    db = SessionLocal()
    try:
        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        if npc:
            npc.emotion_state = emotion
            npc.emotion_intensity = intensity
            db.commit()
            logger.debug(
                f"NPC emotion updated | npc='{npc.name}' | "
                f"emotion={emotion} | intensity={intensity}"
            )
    finally:
        db.close()


def update_npc_relationship(
    npc_id: int,
    entity_key: str,
    score_delta: float,
):
    """
    Updates an NPC's relationship score with another entity.
    entity_key format: "player_1" or "npc_5" or "faction_2"
    score_delta: positive = more positive, negative = more negative
    """
    db = SessionLocal()
    try:
        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        if npc:
            relationships = json.loads(npc.relationships or "{}")
            current = relationships.get(entity_key, 0.0)
            new_score = max(-1.0, min(1.0, current + score_delta))
            relationships[entity_key] = new_score
            npc.relationships = json.dumps(relationships)
            db.commit()
    finally:
        db.close()


def move_npc(npc_id: int, new_location_id: int):
    db = SessionLocal()
    try:
        npc = db.query(NPC).filter(NPC.id == npc_id).first()
        if npc:
            npc.location_id = new_location_id
            db.commit()
    finally:
        db.close()


# ── Player Operations ──────────────────────────────────────────────

def create_player(
    world_id: int,
    username: str,
    character_name: str,
    character_class: str = "adventurer",
    starting_location_id: int = None,
) -> Player:
    db = SessionLocal()
    try:
        player = Player(
            world_id=world_id,
            username=username,
            character_name=character_name,
            character_class=character_class,
            current_location_id=starting_location_id,
            faction_reputation=json.dumps({}),
            inventory=json.dumps([]),
            quest_log=json.dumps({}),
            action_history=json.dumps({}),
        )
        db.add(player)
        db.commit()
        db.refresh(player)
        logger.info(
            f"Player created | id={player.id} | "
            f"username='{username}' | character='{character_name}'"
        )
        return player
    finally:
        db.close()


def get_player(player_id: int) -> Optional[Player]:
    db = SessionLocal()
    try:
        return db.query(Player).filter(
            Player.id == player_id
        ).first()
    finally:
        db.close()


def get_player_by_username(username: str) -> Optional[Player]:
    db = SessionLocal()
    try:
        return db.query(Player).filter(
            Player.username == username
        ).first()
    finally:
        db.close()


def move_player(player_id: int, new_location_id: int):
    db = SessionLocal()
    try:
        player = db.query(Player).filter(
            Player.id == player_id
        ).first()
        if player:
            player.current_location_id = new_location_id
            db.commit()
    finally:
        db.close()


def update_player_stats(player_id: int, updates: dict):
    """Updates player stats (gold, health, experience, etc.)"""
    db = SessionLocal()
    try:
        player = db.query(Player).filter(
            Player.id == player_id
        ).first()
        if player:
            for key, value in updates.items():
                if hasattr(player, key):
                    setattr(player, key, value)
            db.commit()
    finally:
        db.close()


def record_player_action(
    player_id: int,
    world_id: int,
    action_type: str,
    action_detail: str,
    location_id: int = None,
    target_npc_id: int = None,
    world_day: float = 0.0,
    outcome: str = "",
    experience_gained: int = 0,
    gold_change: int = 0,
) -> PlayerAction:
    db = SessionLocal()
    try:
        action = PlayerAction(
            player_id=player_id,
            world_id=world_id,
            action_type=action_type,
            action_detail=action_detail,
            location_id=location_id,
            target_npc_id=target_npc_id,
            world_day=world_day,
            outcome=outcome,
            experience_gained=experience_gained,
            gold_change=gold_change,
        )
        db.add(action)

        # Update player's action history for behavior tracking
        player = db.query(Player).filter(
            Player.id == player_id
        ).first()
        if player:
            history = json.loads(player.action_history or "{}")
            history[action_type] = history.get(action_type, 0) + 1
            player.action_history = json.dumps(history)

        db.commit()
        db.refresh(action)
        return action
    finally:
        db.close()


# ── Faction Operations ─────────────────────────────────────────────

def create_faction(
    world_id: int,
    name: str,
    faction_type: str,
    description: str,
    motto: str = "",
    wealth: int = 1000,
    military_strength: int = 100,
) -> Faction:
    db = SessionLocal()
    try:
        faction = Faction(
            world_id=world_id,
            name=name,
            faction_type=faction_type,
            description=description,
            motto=motto,
            wealth=wealth,
            military_strength=military_strength,
            current_goals=json.dumps([]),
            faction_relations=json.dumps({}),
        )
        db.add(faction)
        db.commit()
        db.refresh(faction)
        logger.info(
            f"Faction created | id={faction.id} | "
            f"name='{name}' | type={faction_type}"
        )
        return faction
    finally:
        db.close()


def get_factions(world_id: int) -> list[Faction]:
    db = SessionLocal()
    try:
        return db.query(Faction).filter(
            Faction.world_id == world_id,
            Faction.is_active == True,
        ).all()
    finally:
        db.close()


# ── Event Operations ───────────────────────────────────────────────

def record_event(
    world_id: int,
    event_type: str,
    title: str,
    description: str,
    world_day: float = 0.0,
    location_id: int = None,
    region_id: int = None,
    player_id: int = None,
    npc_id: int = None,
    faction_id: int = None,
    consequences: list = None,
    is_notable: bool = False,
    importance: int = 1,
) -> WorldEvent:
    """
    Records something that happened in the world.
    This is the world's permanent history.
    """
    db = SessionLocal()
    try:
        event = WorldEvent(
            world_id=world_id,
            event_type=event_type,
            title=title,
            description=description,
            world_day=world_day,
            location_id=location_id,
            region_id=region_id,
            player_id=player_id,
            npc_id=npc_id,
            faction_id=faction_id,
            consequences=json.dumps(consequences or []),
            is_notable=is_notable,
            importance=importance,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        logger.info(
            f"Event recorded | type={event_type} | "
            f"title='{title}' | importance={importance}"
        )
        return event
    finally:
        db.close()


def get_recent_events(
    world_id: int,
    limit: int = 20,
    location_id: int = None,
    event_type: str = None,
    notable_only: bool = False,
) -> list[WorldEvent]:
    db = SessionLocal()
    try:
        query = db.query(WorldEvent).filter(
            WorldEvent.world_id == world_id
        )
        if location_id:
            query = query.filter(
                WorldEvent.location_id == location_id
            )
        if event_type:
            query = query.filter(
                WorldEvent.event_type == event_type
            )
        if notable_only:
            query = query.filter(WorldEvent.is_notable == True)

        return query.order_by(
            WorldEvent.real_timestamp.desc()
        ).limit(limit).all()
    finally:
        db.close()


def get_events_involving_player(
    world_id: int,
    player_id: int,
    limit: int = 50,
) -> list[WorldEvent]:
    db = SessionLocal()
    try:
        return db.query(WorldEvent).filter(
            WorldEvent.world_id == world_id,
            WorldEvent.player_id == player_id,
        ).order_by(
            WorldEvent.real_timestamp.desc()
        ).limit(limit).all()
    finally:
        db.close()


# ── Quest Operations ───────────────────────────────────────────────

def create_quest(
    world_id: int,
    title: str,
    description: str,
    quest_type: str,
    origin_location_id: int = None,
    given_by_npc_id: int = None,
    objectives: list = None,
    rewards: dict = None,
    trigger_conditions: dict = None,
    expires_at_world_day: float = None,
    world_day: float = 0.0,
) -> Quest:
    db = SessionLocal()
    try:
        quest = Quest(
            world_id=world_id,
            title=title,
            description=description,
            quest_type=quest_type,
            origin_location_id=origin_location_id,
            given_by_npc_id=given_by_npc_id,
            objectives=json.dumps(objectives or []),
            rewards=json.dumps(rewards or {}),
            trigger_conditions=json.dumps(trigger_conditions or {}),
            expires_at_world_day=expires_at_world_day,
            created_at_world_day=world_day,
        )
        db.add(quest)
        db.commit()
        db.refresh(quest)
        logger.info(
            f"Quest created | id={quest.id} | "
            f"title='{title}' | type={quest_type}"
        )
        return quest
    finally:
        db.close()


def update_quest_state(
    quest_id: int,
    new_state: str,
    player_id: int = None,
):
    db = SessionLocal()
    try:
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        if quest:
            quest.state = new_state
            if player_id:
                quest.assigned_player_id = player_id
            if new_state == QuestState.COMPLETED:
                quest.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def get_available_quests(
    world_id: int,
    location_id: int = None,
) -> list[Quest]:
    db = SessionLocal()
    try:
        query = db.query(Quest).filter(
            Quest.world_id == world_id,
            Quest.state == QuestState.AVAILABLE,
        )
        if location_id:
            query = query.filter(
                Quest.origin_location_id == location_id
            )
        return query.all()
    finally:
        db.close()


# ── World Summary ──────────────────────────────────────────────────

def get_world_summary(world_id: int) -> dict:
    """
    Returns a complete summary of the world state.
    Used for API responses and LLM context building.
    """
    db = SessionLocal()
    try:
        world = db.query(World).filter(World.id == world_id).first()
        if not world:
            return {}

        regions = db.query(Region).filter(
            Region.world_id == world_id
        ).count()
        locations = db.query(Location).join(
            Region, Location.region_id == Region.id
        ).filter(Region.world_id == world_id).count()
        npcs = db.query(NPC).filter(
            NPC.world_id == world_id,
            NPC.is_alive == True,
        ).count()
        players = db.query(Player).filter(
            Player.world_id == world_id
        ).count()
        factions = db.query(Faction).filter(
            Faction.world_id == world_id,
            Faction.is_active == True,
        ).count()
        quests = db.query(Quest).filter(
            Quest.world_id == world_id,
            Quest.state.in_([
                QuestState.AVAILABLE, QuestState.ACTIVE
            ]),
        ).count()
        events = db.query(WorldEvent).filter(
            WorldEvent.world_id == world_id
        ).count()

        global_state = json.loads(world.global_state or "{}")

        return {
            "id": world.id,
            "name": world.name,
            "description": world.description,
            "world_time": {
                "day": round(world.world_time_days, 2),
                "year": world.world_year,
                "season": world.world_season,
                "time_ratio": world.time_ratio,
            },
            "statistics": {
                "regions": regions,
                "locations": locations,
                "living_npcs": npcs,
                "players": players,
                "active_factions": factions,
                "active_quests": quests,
                "total_events": events,
            },
            "global_state": global_state,
            "created_at": world.created_at.isoformat(),
        }
    finally:
        db.close()