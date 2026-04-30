# Stage 10: Quest Generator - Quick Start Guide

## What Was Built

Stage 10 adds **Procedural Quest Generation** to the AI Game Master Engine. The system generates infinite personalized quests that adapt to each player's behavior, skill level, and the current world state.

### Key Features

✅ **12 Quest Types**: Fetch, Deliver, Kill, Clear, Escort, Investigate, Diplomatic, Craft, Explore, Rescue, Gather, Defend

✅ **Player Personalization**: Quests match player's Bartle type (Explorer, Achiever, Socializer, Killer)

✅ **Skill Scaling**: Difficulty adapts from Novice to Expert

✅ **World Integration**: Quests connect to current world events and faction wars

✅ **Quest Chains**: Multi-quest storylines with escalating difficulty

✅ **NPC Integration**: Quest givers remember interactions via Stage 3 memory system

✅ **Dynamic Rewards**: Gold, XP, faction reputation, and special items

## Files Created

```
backend/quest_generator/
├── __init__.py                 # Module initialization
├── quest_template.py           # Quest type definitions (12 types)
├── quest_personalizer.py       # Player analysis & quest selection
├── quest_builder.py            # LLM-powered content generation
├── quest_chain.py              # Multi-quest sequence management
├── quest_pipeline.py           # Main orchestration
└── README.md                   # Comprehensive documentation

test_quest_generator.py         # Test suite
STAGE_10_QUICKSTART.md         # This file
```

## Quick Test

### 1. Start the Server

```bash
# Make sure you're in the project root
uvicorn backend.main:app --reload
```

### 2. Create a World (if you haven't already)

```bash
curl -X POST "http://localhost:8000/world/create?name=TestWorld&theme=dark%20fantasy"
```

### 3. Create a Player

```bash
curl -X POST "http://localhost:8000/player/create?world_id=1&username=testplayer&character_name=Hero&character_class=adventurer"
```

### 4. Generate Your First Quest

```bash
curl -X POST "http://localhost:8000/quest/generate/1?world_id=1&location_id=1"
```

You should see a complete quest with:
- Title and description
- Quest type and difficulty
- Objectives
- Quest giver dialogue
- Rewards

### 5. Run the Test Suite

```bash
python test_quest_generator.py
```

This will run 7 comprehensive tests:
1. Get all quest types
2. Generate single quest
3. Generate quest chain
4. Get active quests
5. Complete a quest
6. Generate specific quest type
7. Get quests at location

## API Endpoints

### Generate Quest

```http
POST /quest/generate/{player_id}
  ?world_id=1
  &location_id=1
  &quest_type=investigate     # Optional
  &difficulty=hard            # Optional
```

### Generate Quest Chain

```http
POST /quest/generate-chain/{player_id}
  ?world_id=1
  &location_id=1
  &chain_length=3
  &starting_quest_type=kill   # Optional
```

### Get Active Quests

```http
GET /quest/active/{player_id}?world_id=1
```

### Complete Quest

```http
POST /quest/complete/{quest_id}
  ?player_id=1
  &world_id=1
  &completion_method=diplomatic
```

### Get Quest Types

```http
GET /quest/types
```

### Get Quests at Location

```http
GET /quest/available/{location_id}?world_id=1&player_id=1
```

## Example: Full Quest Flow

```bash
# 1. Generate a quest
QUEST=$(curl -s -X POST "http://localhost:8000/quest/generate/1?world_id=1&location_id=1")
QUEST_ID=$(echo $QUEST | jq -r '.id')

echo "Generated Quest ID: $QUEST_ID"
echo "Title: $(echo $QUEST | jq -r '.title')"

# 2. Get active quests
curl "http://localhost:8000/quest/active/1?world_id=1" | jq '.quests[] | {id, title, type}'

# 3. Complete the quest
curl -X POST "http://localhost:8000/quest/complete/$QUEST_ID?player_id=1&world_id=1&completion_method=combat" | jq

# 4. Check rewards
curl "http://localhost:8000/player/1/context?world_id=1" | jq '.player | {gold, experience, level}'
```

## Integration with Other Stages

### Stage 3: NPC Memory
- Quest givers remember offering quests
- NPCs remember quest completions
- Relationship scores affect quest availability

### Stage 4: Narrative Engine
- Player's Bartle type determines quest types
- Quests connect to active story arcs

### Stage 5: Behavior Prediction
- Skill assessment determines difficulty
- Engagement scorer influences quest frequency

### Stage 7: Economy & Factions
- Faction wars affect quest types
- Economy state influences rewards

### Stage 9: GM System
- Content Director suggests quest generation
- NPC Orchestrator identifies quest givers

## Quest Types Explained

| Type | Description | Example |
|------|-------------|---------|
| **Fetch** | Retrieve item from location | "Find the ancient tome in the ruins" |
| **Deliver** | Transport item to NPC | "Deliver this letter to the king" |
| **Kill** | Eliminate specific enemy | "Slay the bandit leader" |
| **Clear** | Clear location of enemies | "Clear the dungeon of all monsters" |
| **Escort** | Protect NPC during journey | "Escort the merchant to the city" |
| **Investigate** | Uncover mystery | "Discover who murdered the merchant" |
| **Diplomatic** | Negotiate between factions | "Broker peace between the guilds" |
| **Craft** | Create specific item | "Forge a legendary sword" |
| **Explore** | Discover new location | "Find the hidden valley" |
| **Rescue** | Save captured NPC | "Rescue the prisoner from the castle" |
| **Gather** | Collect multiple resources | "Gather 10 rare herbs" |
| **Defend** | Protect location from attack | "Defend the village from raiders" |

## Difficulty Levels

| Level | Description | Gold | XP | Danger |
|-------|-------------|------|-----|--------|
| **Trivial** | Tutorial-level | 0.5x | 0.5x | 1 |
| **Easy** | Beginner-friendly | 1.0x | 1.0x | 2 |
| **Moderate** | Standard challenge | 1.5x | 1.5x | 4 |
| **Hard** | Experienced players | 2.5x | 2.5x | 6 |
| **Very Hard** | Expert-level | 4.0x | 4.0x | 8 |
| **Legendary** | Master-level | 10.0x | 10.0x | 10 |

## Completion Methods

How you complete a quest affects future content:

- **Combat**: Violent approach, affects reputation with peaceful factions
- **Stealth**: Subtle approach, gains favor with thieves
- **Diplomatic**: Negotiation, gains favor with nobles
- **Standard**: Default completion

## Troubleshooting

### Quest Generation Fails

**Problem**: Quest generation returns 500 error

**Solutions**:
1. Check if LLM API key is set in `.env`
2. Verify player exists: `GET /player/{player_id}/context`
3. Verify location exists: `GET /location/{location_id}/context`
4. Check server logs for detailed error

### No Quest Giver Assigned

**Problem**: Quest has `quest_giver_id: null`

**Solutions**:
1. Generate NPCs at the location first
2. Use `POST /generate/npc` to create NPCs
3. Set `assign_to_npc=false` if you don't need a quest giver

### Quest Not Appearing in Active Quests

**Problem**: Generated quest doesn't show in `/quest/active`

**Solutions**:
1. Check quest state (should be "available" or "active")
2. Verify `assigned_player_id` matches your player
3. Check if quest expired (time-limited quests)

## Next Steps

### Stage 11: World Memory & Lore Engine (GraphRAG)

The next stage will add:
- Knowledge graph of all world history
- Natural language queries: "What happened to the merchant?"
- Quest lore connections to world timeline
- Multi-hop reasoning across events

### Stage 12: Full Stack Game Interface

The final stage will add:
- React game interface
- Real-time quest log UI
- Interactive quest objectives
- Visual quest map
- NPC dialogue interface

## Performance

- **Single quest generation**: ~2-3 seconds (LLM call)
- **Quest chain generation**: ~5-8 seconds
- **Quest retrieval**: <100ms
- **Quest completion**: <200ms

## Documentation

Full documentation available in:
- `backend/quest_generator/README.md` - Complete technical documentation
- API docs: http://localhost:8000/docs (when server running)

## Testing

Run the comprehensive test suite:

```bash
python test_quest_generator.py
```

Expected output:
```
Tests Passed: 7/7

  ✅ PASS  Quest Types
  ✅ PASS  Single Quest
  ✅ PASS  Quest Chain
  ✅ PASS  Active Quests
  ✅ PASS  Complete Quest
  ✅ PASS  Investigate Quest
  ✅ PASS  Location Quests

🎉 All tests passed! Quest Generator is working perfectly!
```

## Example Quest Output

```json
{
  "id": 42,
  "title": "The Missing Merchant",
  "description": "A local merchant has vanished under mysterious circumstances. His family fears the worst and needs someone to investigate his disappearance.",
  "quest_type": "investigate",
  "difficulty": "moderate",
  "objectives": [
    "Interview witnesses at the market square",
    "Search the merchant's home for clues",
    "Follow the trail to the forest edge",
    "Discover the truth about his disappearance"
  ],
  "quest_giver_dialogue": {
    "introduction": "Please, you must help us! My husband disappeared three days ago. The guards won't investigate, but I know something terrible has happened.",
    "acceptance": "Thank you! Time is of the essence. Start at the market where he was last seen.",
    "reminder": "Have you found any clues? Please hurry, I fear the worst.",
    "completion": "You found him! I cannot thank you enough. Here, take this reward - you've earned it."
  },
  "rewards": {
    "gold": 150,
    "experience": 300,
    "reputation_changes": {
      "1": 10
    },
    "special_reward": "Merchant's Gratitude Token"
  },
  "danger_level": 4,
  "has_time_pressure": false,
  "expires_in_days": null,
  "lore_connection": "Connected to recent bandit activity in the region. The Shadow Conclave may be involved."
}
```

## Congratulations! 🎉

You've successfully built Stage 10 of the AI Game Master Engine. The quest generator creates infinite personalized content that adapts to each player's unique play style and the evolving world state.

**What makes this special:**
- Every quest is unique and personalized
- Quests connect to world events and lore
- NPCs remember quest interactions
- Quest chains tell cohesive stories
- Difficulty scales with player skill

**Ready for Stage 11?**

Stage 11 will add GraphRAG to create a queryable knowledge graph of all world history, making the world truly remember everything that has happened.
