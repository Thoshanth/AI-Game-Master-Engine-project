import json
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Float, DateTime, Text, Boolean, ForeignKey,
    JSON, Enum as SAEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum

DATABASE_URL = "sqlite:///./game_world.db"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ── Enums ──────────────────────────────────────────────────────────

class TerrainType(str, enum.Enum):
    FOREST = "forest"
    MOUNTAIN = "mountain"
    PLAINS = "plains"
    DESERT = "desert"
    SWAMP = "swamp"
    COASTAL = "coastal"
    TUNDRA = "tundra"


class LocationType(str, enum.Enum):
    CITY = "city"
    VILLAGE = "village"
    DUNGEON = "dungeon"
    TAVERN = "tavern"
    CASTLE = "castle"
    RUINS = "ruins"
    WILDERNESS = "wilderness"
    MINE = "mine"
    TEMPLE = "temple"
    MARKET = "market"


class NPCRole(str, enum.Enum):
    MERCHANT = "merchant"
    GUARD = "guard"
    INNKEEPER = "innkeeper"
    BLACKSMITH = "blacksmith"
    MAGE = "mage"
    PRIEST = "priest"
    THIEF = "thief"
    NOBLE = "noble"
    PEASANT = "peasant"
    WARRIOR = "warrior"
    QUEST_GIVER = "quest_giver"
    VILLAIN = "villain"
    COMPANION = "companion"


class EmotionState(str, enum.Enum):
    HAPPY = "happy"
    NEUTRAL = "neutral"
    SUSPICIOUS = "suspicious"
    ANGRY = "angry"
    FEARFUL = "fearful"
    SAD = "sad"
    EXCITED = "excited"
    GRATEFUL = "grateful"
    HOSTILE = "hostile"


class FactionRelation(str, enum.Enum):
    ALLIED = "allied"
    FRIENDLY = "friendly"
    NEUTRAL = "neutral"
    UNFRIENDLY = "unfriendly"
    HOSTILE = "hostile"
    AT_WAR = "at_war"


class QuestState(str, enum.Enum):
    HIDDEN = "hidden"
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class EventType(str, enum.Enum):
    PLAYER_ACTION = "player_action"
    NPC_ACTION = "npc_action"
    FACTION_ACTION = "faction_action"
    WORLD_EVENT = "world_event"
    COMBAT = "combat"
    TRADE = "trade"
    DIALOGUE = "dialogue"
    QUEST_UPDATE = "quest_update"
    DEATH = "death"
    DISCOVERY = "discovery"


# ── World ──────────────────────────────────────────────────────────

class World(Base):
    """
    The top-level container for everything.
    One database can hold multiple worlds.
    """
    __tablename__ = "worlds"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # World clock
    world_time_days = Column(Float, default=0.0)
    world_season = Column(String, default="spring")
    world_year = Column(Integer, default=1)
    real_time_start = Column(DateTime, default=datetime.utcnow)

    # World configuration
    # How many real seconds = 1 world day
    time_ratio = Column(Float, default=3600.0)

    # Global world state as JSON
    # Stores: active_wars, economic_state, major_events_summary
    global_state = Column(Text, default="{}")

    # Relationships
    regions = relationship("Region", back_populates="world")
    factions = relationship("Faction", back_populates="world")
    players = relationship("Player", back_populates="world")
    events = relationship("WorldEvent", back_populates="world")


# ── Region ─────────────────────────────────────────────────────────

class Region(Base):
    """
    A geographic area of the world.
    Contains multiple locations.
    """
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"))
    name = Column(String)
    description = Column(Text)
    terrain_type = Column(String, default=TerrainType.PLAINS)
    danger_level = Column(Integer, default=1)  # 1-10
    climate = Column(String, default="temperate")

    # Resources available in this region
    resources = Column(Text, default="[]")  # JSON list

    # Position on world map (0-100 grid)
    map_x = Column(Float, default=50.0)
    map_y = Column(Float, default=50.0)

    # Controlling faction
    controlling_faction_id = Column(
        Integer, ForeignKey("factions.id"), nullable=True
    )

    world = relationship("World", back_populates="regions")
    locations = relationship("Location", back_populates="region")


# ── Location ───────────────────────────────────────────────────────

class Location(Base):
    """
    A specific place in the world.
    Where everything actually happens.
    """
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"))
    name = Column(String)
    location_type = Column(String, default=LocationType.VILLAGE)
    description = Column(Text)

    # Population and economy
    population = Column(Integer, default=0)
    wealth_level = Column(Integer, default=5)  # 1-10
    safety_level = Column(Integer, default=5)  # 1-10

    # Current state
    is_accessible = Column(Boolean, default=True)
    current_events = Column(Text, default="[]")  # JSON list

    # Map position within region
    map_x = Column(Float, default=50.0)
    map_y = Column(Float, default=50.0)

    # Lore
    history = Column(Text, default="")
    rumors = Column(Text, default="[]")  # JSON list

    region = relationship("Region", back_populates="locations")
    npcs = relationship("NPC", back_populates="location")
    items = relationship("Item", back_populates="location")
    quests = relationship("Quest", back_populates="origin_location")


# ── NPC ────────────────────────────────────────────────────────────

class NPC(Base):
    """
    A non-player character with full personality,
    memory, and autonomous behavior capability.
    """
    __tablename__ = "npcs"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    faction_id = Column(
        Integer, ForeignKey("factions.id"), nullable=True
    )

    # Identity
    name = Column(String)
    age = Column(Integer, default=30)
    gender = Column(String, default="neutral")
    role = Column(String, default=NPCRole.PEASANT)
    appearance = Column(Text)
    backstory = Column(Text)

    # Personality (Big Five traits, each 1-10)
    trait_openness = Column(Float, default=5.0)
    trait_conscientiousness = Column(Float, default=5.0)
    trait_extraversion = Column(Float, default=5.0)
    trait_agreeableness = Column(Float, default=5.0)
    trait_neuroticism = Column(Float, default=5.0)

    # Current emotional state
    emotion_state = Column(String, default=EmotionState.NEUTRAL)
    emotion_intensity = Column(Float, default=0.5)  # 0.0-1.0

    # Current activity
    current_activity = Column(String, default="idle")
    schedule = Column(Text, default="{}")  # JSON: hour → activity

    # Relationships with other entities
    # JSON: {entity_type}_{entity_id} → relationship_score (-1 to 1)
    relationships = Column(Text, default="{}")

    # Knowledge — what this NPC knows about the world
    known_facts = Column(Text, default="[]")  # JSON list
    known_secrets = Column(Text, default="[]")  # JSON list
    known_rumors = Column(Text, default="[]")  # JSON list

    # Stats for combat/skill resolution
    health = Column(Integer, default=100)
    max_health = Column(Integer, default=100)
    strength = Column(Integer, default=10)
    intelligence = Column(Integer, default=10)
    charisma = Column(Integer, default=10)

    # Is NPC alive?
    is_alive = Column(Boolean, default=True)
    death_time = Column(DateTime, nullable=True)
    death_cause = Column(String, nullable=True)

    # ChromaDB collection ID for vector memory
    memory_collection_id = Column(String, nullable=True)

    location = relationship("Location", back_populates="npcs")


# ── Player ─────────────────────────────────────────────────────────

class Player(Base):
    """
    A human player in the game world.
    Tracks everything they've done and experienced.
    """
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"))
    current_location_id = Column(
        Integer, ForeignKey("locations.id"), nullable=True
    )

    # Identity
    username = Column(String, unique=True, index=True)
    character_name = Column(String)
    character_class = Column(String, default="adventurer")
    backstory = Column(Text, default="")

    # Stats
    level = Column(Integer, default=1)
    experience = Column(Integer, default=0)
    health = Column(Integer, default=100)
    max_health = Column(Integer, default=100)
    gold = Column(Integer, default=50)
    strength = Column(Integer, default=10)
    intelligence = Column(Integer, default=10)
    charisma = Column(Integer, default=10)
    stealth = Column(Integer, default=10)

    # Reputation with factions
    # JSON: faction_id → reputation_score (-100 to 100)
    faction_reputation = Column(Text, default="{}")

    # Inventory
    # JSON: list of item_ids
    inventory = Column(Text, default="[]")

    # Quest log
    # JSON: {quest_id → state}
    quest_log = Column(Text, default="{}")

    # Player behavior data for ML prediction
    # JSON: {action_type → count}
    action_history = Column(Text, default="{}")

    # Player type classification
    # explorer, achiever, socializer, killer
    player_type = Column(String, nullable=True)
    player_type_confidence = Column(Float, default=0.0)

    # Session tracking
    total_sessions = Column(Integer, default=0)
    total_playtime_seconds = Column(Integer, default=0)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ChromaDB collection for player's personal memories
    memory_collection_id = Column(String, nullable=True)

    world = relationship("World", back_populates="players")
    actions = relationship("PlayerAction", back_populates="player")


# ── Faction ────────────────────────────────────────────────────────

class Faction(Base):
    """
    An organization in the world with goals,
    resources, and autonomous behavior.
    """
    __tablename__ = "factions"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"))

    # Identity
    name = Column(String)
    faction_type = Column(String)  # kingdom, guild, cult, etc.
    description = Column(Text)
    motto = Column(String, default="")
    symbol = Column(String, default="")

    # Resources
    wealth = Column(Integer, default=1000)
    military_strength = Column(Integer, default=100)
    political_influence = Column(Integer, default=50)
    population_under_control = Column(Integer, default=0)

    # Goals — what this faction is trying to achieve
    # JSON: list of goal objects
    current_goals = Column(Text, default="[]")

    # Relations with other factions
    # JSON: faction_id → FactionRelation
    faction_relations = Column(Text, default="{}")

    # Headquarters location
    headquarters_id = Column(
        Integer, ForeignKey("locations.id"), nullable=True
    )

    # Is faction active?
    is_active = Column(Boolean, default=True)

    world = relationship("World", back_populates="factions")


# ── Quest ──────────────────────────────────────────────────────────

class Quest(Base):
    """
    A task in the world with trigger conditions,
    objectives, and a state machine.
    """
    __tablename__ = "quests"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"))
    origin_location_id = Column(
        Integer, ForeignKey("locations.id"), nullable=True
    )
    given_by_npc_id = Column(
        Integer, ForeignKey("npcs.id"), nullable=True
    )

    # Identity
    title = Column(String)
    description = Column(Text)
    quest_type = Column(String)  # main, side, faction, hidden, emergency

    # State machine
    state = Column(String, default=QuestState.HIDDEN)

    # Trigger conditions
    # JSON: conditions that must be met for quest to become available
    trigger_conditions = Column(Text, default="{}")

    # Objectives
    # JSON: list of objective objects with completion tracking
    objectives = Column(Text, default="[]")

    # Rewards
    # JSON: {gold, experience, items, reputation_changes}
    rewards = Column(Text, default="{}")

    # Which player has this quest (null = world quest, any player can take)
    assigned_player_id = Column(
        Integer, ForeignKey("players.id"), nullable=True
    )

    # Time pressure
    expires_at_world_day = Column(Float, nullable=True)

    created_at_world_day = Column(Float, default=0.0)
    completed_at = Column(DateTime, nullable=True)

    origin_location = relationship(
        "Location", back_populates="quests"
    )


# ── Item ───────────────────────────────────────────────────────────

class Item(Base):
    """
    An object in the world that can be owned, traded, used.
    """
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"))
    location_id = Column(
        Integer, ForeignKey("locations.id"), nullable=True
    )

    # Identity
    name = Column(String)
    item_type = Column(String)  # weapon, armor, potion, key, treasure, tool
    description = Column(Text)
    rarity = Column(String, default="common")  # common, uncommon, rare, legendary

    # Stats
    value = Column(Integer, default=1)
    weight = Column(Float, default=1.0)

    # Properties as JSON (damage, defense, effects, etc.)
    properties = Column(Text, default="{}")

    # Ownership
    owner_player_id = Column(
        Integer, ForeignKey("players.id"), nullable=True
    )
    owner_npc_id = Column(
        Integer, ForeignKey("npcs.id"), nullable=True
    )

    # Item history
    previous_owners = Column(Text, default="[]")  # JSON list
    lore = Column(Text, default="")

    location = relationship("Location", back_populates="items")


# ── World Event ────────────────────────────────────────────────────

class WorldEvent(Base):
    """
    Something that happened in the world.
    The complete history of the world is stored here.
    Every significant action creates an event.
    """
    __tablename__ = "world_events"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"))

    # When
    real_timestamp = Column(DateTime, default=datetime.utcnow)
    world_day = Column(Float, default=0.0)

    # What
    event_type = Column(String)
    title = Column(String)
    description = Column(Text)

    # Where
    location_id = Column(
        Integer, ForeignKey("locations.id"), nullable=True
    )
    region_id = Column(
        Integer, ForeignKey("regions.id"), nullable=True
    )

    # Who was involved
    player_id = Column(
        Integer, ForeignKey("players.id"), nullable=True
    )
    npc_id = Column(
        Integer, ForeignKey("npcs.id"), nullable=True
    )
    faction_id = Column(
        Integer, ForeignKey("factions.id"), nullable=True
    )

    # Consequences — what this event caused
    # JSON: list of consequence objects
    consequences = Column(Text, default="[]")

    # Was this a significant event that NPCs will talk about?
    is_notable = Column(Boolean, default=False)

    # Importance score 0-10
    importance = Column(Integer, default=1)

    world = relationship("World", back_populates="events")


# ── Player Action ──────────────────────────────────────────────────

class PlayerAction(Base):
    """
    Every significant action a player takes.
    Used for behavior analysis and ML prediction.
    """
    __tablename__ = "player_actions"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    world_id = Column(Integer, ForeignKey("worlds.id"))

    # What they did
    action_type = Column(String)
    action_detail = Column(Text)

    # Context
    location_id = Column(
        Integer, ForeignKey("locations.id"), nullable=True
    )
    target_npc_id = Column(
        Integer, ForeignKey("npcs.id"), nullable=True
    )
    world_day = Column(Float, default=0.0)
    real_timestamp = Column(DateTime, default=datetime.utcnow)

    # Outcome
    outcome = Column(Text, default="")
    experience_gained = Column(Integer, default=0)
    gold_change = Column(Integer, default=0)

    player = relationship("Player", back_populates="actions")


# ── Faction Relation ───────────────────────────────────────────────

class FactionRelationship(Base):
    """
    Tracks relationships between factions with full history.
    """
    __tablename__ = "faction_relationships"

    id = Column(Integer, primary_key=True, index=True)
    world_id = Column(Integer, ForeignKey("worlds.id"))
    faction_a_id = Column(Integer, ForeignKey("factions.id"))
    faction_b_id = Column(Integer, ForeignKey("factions.id"))

    relation = Column(String, default=FactionRelation.NEUTRAL)
    relation_score = Column(Float, default=0.0)  # -100 to 100

    # History of relation changes
    history = Column(Text, default="[]")  # JSON list

    updated_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    from backend.logger import get_logger
    logger = get_logger("database")
    logger.info("World state database initialized")