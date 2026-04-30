# Stage 10: Procedural Quest Generator

## Overview

The Procedural Quest Generator creates personalized, lore-consistent quests that adapt to each player's behavior, skill level, and the current world state. Every quest is unique and connects to ongoing world events.

## Architecture

```
quest_pipeline.py (Main Entry Point)
    ↓
quest_personalizer.py (Player Analysis)
    ↓
quest_builder.py (LLM Generation)
    ↓
quest_template.py (Structure & Validation)
    ↓
quest_chain.py (Multi-Quest Sequences)
```

## Key Features

### 1. Player-Personalized Quests

Quests adapt to player's **Bartle Type**:
- **Explorer**: Investigation, discovery, lore-heavy quests
- **Achiever**: Clear objectives, rare items, progression rewards
- **Socializer**: NPC relationships, faction politics, dialogue choices
- **Killer**: Combat encounters, conquest, powerful weapons

### 2. Skill-Appropriate Difficulty

Quests scale to player skill level:
- **Novice**: Simple fetch quests, clear directions, low danger
- **Beginner**: Moderate challenges, some ambiguity
- **Intermediate**: Multi-step quests, hidden content
- **Advanced**: Complex faction politics, lateral thinking
- **Expert**: Hidden chains, mastery-level secrets

### 3. World-State Integration

Quests connect to current world events:
- During faction wars → combat and diplomatic quests increase
- After mysterious events → investigation quests appear
- Economic crises → trade and gather quests emerge
- NPC deaths → revenge and rescue quests trigger

### 4. Quest Types (12 Total)

| Type | Description | Best For |
|------|-------------|----------|
| **Fetch** | Retrieve item from location | Achievers, Explorers |
| **Deliver** | Transport item to NPC | Achievers, Socializers |
| **Kill** | Eliminate specific enemy | Killers, Achievers |
| **Clear** | Clear location of all enemies | Killers, Achievers |
| **Escort** | Protect NPC during journey | Socializers, Killers |
| **Investigate** | Uncover mystery | Explorers, Socializers |
| **Diplomatic** | Negotiate between factions | Socializers, Achievers |
| **Craft** | Create specific item | Achievers, Explorers |
| **Explore** | Discover new location | Explorers, Achievers |
| **Rescue** | Save captured NPC | All types |
| **Gather** | Collect multiple resources | Achievers, Explorers |
| **Defend** | Protect location from attack | Killers, Achievers |

### 5. Quest Chains

Multi-quest storylines with:
- **Linear progression**: Quest 1 → 2 → 3
- **Escalating difficulty**: Each quest harder than previous
- **Branching paths**: Completion method affects next quest
- **Shared narrative**: Cohesive story across all quests
- **Climactic finale**: Final quest resolves the arc

### 6. Dynamic Rewards

Rewards scale with difficulty:
- **Gold**: 0.5x to 10x base amount
- **Experience**: 0.5x to 10x base amount
- **Faction Reputation**: Positive/negative changes
- **Special Items**: Unique rewards for hard quests
- **Lore Unlocks**: Secrets and world knowledge

## API Endpoints

### Generate Single Quest

```http
POST /quest/generate/{player_id}
```

**Parameters:**
- `world_id`: World ID
- `location_id`: Starting location
- `quest_type`: (optional) Force specific type
- `difficulty`: (optional) Force specific difficulty

**Response:**
```json
{
  "id": 42,
  "title": "The Missing Merchant",
  "description": "A local merchant has vanished...",
  "quest_type": "investigate",
  "difficulty": "moderate",
  "objectives": [
    "Interview witnesses at the market",
    "Search the merchant's home",
    "Follow the trail to the forest"
  ],
  "quest_giver_dialogue": {
    "introduction": "Please, you must help...",
    "acceptance": "Thank you! Time is of the essence.",
    "completion": "You found him! I'm forever grateful."
  },
  "rewards": {
    "gold": 150,
    "experience": 300,
    "reputation_changes": {
      "1": 10
    }
  },
  "expires_in_days": null,
  "lore_connection": "Connected to recent bandit activity"
}
```

### Generate Quest Chain

```http
POST /quest/generate-chain/{player_id}
```

**Parameters:**
- `world_id`: World ID
- `location_id`: Starting location
- `chain_length`: 2-5 quests (default: 3)
- `starting_quest_type`: (optional) Type for first quest

**Response:**
```json
{
  "chain_length": 3,
  "quests": [
    {
      "id": 42,
      "title": "Shadows in the Market",
      "chain_position": 1,
      "unlocks_quest": 2
    },
    {
      "id": 43,
      "title": "The Conspiracy Deepens",
      "chain_position": 2,
      "unlocks_quest": 3
    },
    {
      "id": 44,
      "title": "Confronting the Shadow Lord",
      "chain_position": 3,
      "unlocks_quest": null
    }
  ]
}
```

### Get Active Quests

```http
GET /quest/active/{player_id}?world_id={world_id}
```

Returns all quests in `available` or `active` state.

### Complete Quest

```http
POST /quest/complete/{quest_id}
```

**Parameters:**
- `player_id`: Player ID
- `world_id`: World ID
- `completion_method`: `combat`, `stealth`, `diplomatic`, or `standard`

**Response:**
```json
{
  "quest_id": 42,
  "quest_title": "The Missing Merchant",
  "rewards_granted": {
    "gold": 150,
    "experience": 300,
    "reputation_changes": {
      "1": 10
    }
  },
  "completion_method": "diplomatic"
}
```

### Fail Quest

```http
POST /quest/fail/{quest_id}
```

**Parameters:**
- `player_id`: Player ID
- `world_id`: World ID
- `reason`: `abandoned`, `expired`, `failed_objective`, or `death`

### Get Quest Types

```http
GET /quest/types
```

Returns all 12 quest types with descriptions and requirements.

### Get Available Quests at Location

```http
GET /quest/available/{location_id}?world_id={world_id}&player_id={player_id}
```

Returns all quests available at a specific location.

## How Quest Generation Works

### Step-by-Step Process

1. **Player Analysis**
   - Load player's Bartle type (from Stage 4)
   - Assess player skill level (from Stage 5)
   - Check recent quest history (avoid repetition)

2. **Quest Type Selection**
   - Match quest type to player's Bartle type
   - Weight by current world state (wars → combat quests)
   - Filter out recently completed types

3. **Difficulty Selection**
   - Map skill level to difficulty
   - Occasionally increase for variety (20% chance)

4. **Context Building**
   - Gather world state (recent events, factions, NPCs)
   - Get player's faction relationships
   - Get location details and atmosphere

5. **LLM Generation**
   - Send context to LLM with structured prompt
   - Generate title, description, objectives, dialogue
   - Ensure lore consistency with world events

6. **Quest Giver Assignment**
   - Find NPCs at location
   - Prefer NPCs with appropriate role
   - Check relationship with player (avoid hostile NPCs)

7. **Database Storage**
   - Save quest to database
   - Update player's quest log
   - Store memory in quest giver NPC

8. **World Event Recording**
   - Record quest creation as world event
   - Broadcast to online players (if multiplayer)

## Integration with Other Stages

### Stage 1: World State Engine
- Reads world entities (NPCs, locations, factions)
- Stores quests in database
- Updates player quest log

### Stage 3: NPC Memory System
- Quest givers remember offering quests
- NPCs remember quest completions
- Relationship scores affect quest availability

### Stage 4: Dynamic Narrative Engine
- Quests connect to active story arcs
- Quest outcomes create consequences
- Player profile determines quest types

### Stage 5: Player Behavior Predictor
- Skill assessment determines difficulty
- Engagement scorer influences quest frequency
- Frustration detector triggers easier quests

### Stage 7: Economy & Faction Simulation
- Faction wars affect quest types
- Economy state influences rewards
- Faction reputation gates certain quests

### Stage 9: GM Agent System
- Content Director suggests quest generation
- NPC Orchestrator identifies quest givers
- Narrator describes quest locations

## Quest Chain System

### Linear Chains

```
Quest 1 (Easy) → Quest 2 (Moderate) → Quest 3 (Hard)
```

Each quest unlocks the next. Difficulty escalates.

### Branching Chains

```
Quest 1 (Base)
  ├─> Honorable Path: Quest 2A → Quest 3A
  └─> Ruthless Path: Quest 2B → Quest 3B
```

Completion method determines branch.

### Adaptive Chains

Quests adapt based on previous completion:
- **Combat completion** → Next quest has combat focus
- **Stealth completion** → Next quest rewards subtlety
- **Diplomatic completion** → Next quest involves negotiation

## Quest State Machine

```
HIDDEN → AVAILABLE → ACTIVE → COMPLETED
                  ↓
                FAILED
                  ↓
                EXPIRED
```

- **HIDDEN**: Quest exists but player hasn't met trigger conditions
- **AVAILABLE**: Quest offered by NPC, player can accept
- **ACTIVE**: Player accepted, objectives in progress
- **COMPLETED**: All objectives met, rewards granted
- **FAILED**: Player failed critical objective
- **EXPIRED**: Time limit ran out

## Trigger Conditions

Quests can have unlock requirements:

```json
{
  "trigger_conditions": {
    "min_level": 5,
    "faction_reputation": {
      "1": 20
    },
    "prerequisite_quests": [41],
    "world_state": {
      "faction_1_at_war": true
    }
  }
}
```

## Time Pressure

Some quests have time limits:

- **Hard quests**: 7 world days
- **Very Hard quests**: 5 world days
- **Legendary quests**: 3 world days

Expired quests auto-fail with consequences.

## Completion Methods

How a quest is completed affects future content:

| Method | Reputation Impact | Next Quest Hint |
|--------|-------------------|-----------------|
| **Combat** | Military +10, Peaceful -5 | "Your violent approach has been noted" |
| **Stealth** | Thieves +10 | "Your subtlety impressed the right people" |
| **Diplomatic** | Nobles +10, Merchants +5 | "Your silver tongue opens new doors" |
| **Standard** | No special impact | Default progression |

## Example: Full Quest Generation Flow

```python
# 1. Player enters a new location
player_id = 1
world_id = 1
location_id = 5

# 2. Generate personalized quest
quest = generate_personalized_quest(
    player_id=player_id,
    world_id=world_id,
    location_id=location_id,
)

# Quest is automatically:
# - Matched to player's Bartle type (Explorer)
# - Scaled to player's skill level (Intermediate)
# - Connected to recent world events (Faction war)
# - Assigned to appropriate NPC (Quest giver at location)
# - Stored in database with unique ID

# 3. Player accepts quest
# (Quest state: AVAILABLE → ACTIVE)

# 4. Player completes objectives
# (Track progress in quest log)

# 5. Player returns to quest giver
result = complete_quest(
    quest_id=quest["id"],
    player_id=player_id,
    world_id=world_id,
    completion_method="diplomatic",
)

# Rewards granted:
# - Gold: 150
# - Experience: 300
# - Faction reputation: +10 with Nobles
# - NPC memory: Quest giver remembers success
# - World event: Quest completion recorded
```

## Testing

### Test Quest Generation

```bash
# Start server
uvicorn backend.main:app --reload

# Generate quest for player 1
curl -X POST "http://localhost:8000/quest/generate/1?world_id=1&location_id=1"

# Generate quest chain
curl -X POST "http://localhost:8000/quest/generate-chain/1?world_id=1&location_id=1&chain_length=3"

# Get active quests
curl "http://localhost:8000/quest/active/1?world_id=1"

# Complete quest
curl -X POST "http://localhost:8000/quest/complete/1?player_id=1&world_id=1&completion_method=combat"
```

### Test Quest Types

```bash
# Get all quest types
curl "http://localhost:8000/quest/types"

# Generate specific type
curl -X POST "http://localhost:8000/quest/generate/1?world_id=1&location_id=1&quest_type=investigate"

# Generate specific difficulty
curl -X POST "http://localhost:8000/quest/generate/1?world_id=1&location_id=1&difficulty=legendary"
```

## Future Enhancements (Stage 11+)

- **Quest Lore Graph**: Connect quests to GraphRAG knowledge graph
- **Procedural Quest Locations**: Generate new locations for quests
- **Dynamic Quest Objectives**: Objectives that change based on world events
- **Multiplayer Quest Sharing**: Quests that require multiple players
- **Quest Reputation System**: NPCs remember quest failures
- **Seasonal Quests**: Time-limited quests tied to world seasons

## Files

- `quest_template.py`: Quest type definitions and templates
- `quest_personalizer.py`: Player analysis and quest selection
- `quest_builder.py`: LLM-powered content generation
- `quest_chain.py`: Multi-quest sequence management
- `quest_pipeline.py`: Main orchestration and database operations
- `__init__.py`: Module initialization

## Dependencies

- **Stage 1**: World state database
- **Stage 3**: NPC memory system
- **Stage 4**: Player profiler (Bartle types)
- **Stage 5**: Skill assessor
- **LLM Client**: NVIDIA Nemotron 120B via OpenRouter

## Logging

All quest operations are logged:

```
[quest_generator.pipeline] Generating quest | player=1 | world=1 | location=5
[quest_generator.personalizer] Quest type selected | player_id=1 | player_type=explorer | quest_type=investigate
[quest_generator.builder] Quest generated | title='The Missing Merchant'
[quest_generator.pipeline] Quest generated | id=42 | title='The Missing Merchant' | type=investigate
```

## Performance

- **Single quest generation**: ~2-3 seconds (LLM call)
- **Quest chain generation**: ~5-8 seconds (multiple LLM calls)
- **Quest retrieval**: <100ms (database query)
- **Quest completion**: <200ms (database update + memory storage)

## Conclusion

Stage 10 transforms the game from a static world with hand-written quests into a dynamic world that generates infinite personalized content. Every player gets quests tailored to their play style, skill level, and the current state of the world.

**Next Stage**: Stage 11 will add GraphRAG to create a queryable knowledge graph of all world history, allowing players to ask "what happened to the merchant I met 3 weeks ago?" and get accurate, connected answers.
