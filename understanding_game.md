# AI Engineering Learning Roadmap
## Project 3: AI Game Master Engine
### Complete Understanding & Roadmap Document

**Student:** M.S.N. Thoshanth Reddy  
**Institution:** B.Tech | HITAM, Hyderabad  
**Document:** AI Engineering Roadmap • April 2026

---

## 1. Your AI Engineering Portfolio

You have built three production-grade AI engineering projects from scratch. Each project introduces completely new concepts and tools while reinforcing everything from previous projects. This document explains every stage you have completed in Project 3, what you will build next, and how everything connects.

### 1.1 Three-Project Portfolio Summary

| Project | Name | Key Concepts |
|---|---|---|
| Project 1 ✅ | AI Research Assistant | RAG, ChromaDB, LlamaIndex, LangGraph, Docker, 10 stages |
| Project 2 ✅ | AI Medical Platform | Medical NLP, FHIR, Drug Interactions, 5-Agent Clinical System, RAGAS, 12 stages |
| Project 3 🔄 | AI Game Master Engine | Autonomous World, NPC Memory, Multi-Player, Economy Sim, Combat, GM Agents, 12 stages |

---

## 2. Project 3 — Stages Completed (1–9)

All 9 stages below are fully implemented and working. Each stage explanation tells you WHAT it does, WHY it matters, and HOW it connects to other stages.

| Stage | Name | What It Does | Status |
|---|---|---|---|
| 1 | World State Engine | 10 SQLAlchemy entities. World clock. Faction + NPC + Player + Quest database. 13 API endpoints. | ✅ Done |
| 2 | Procedural Generator | LLM-powered biome-aware location/NPC/item/event generation. Dungeon with 3 floors + boss + loot. | ✅ Done |
| 3 | NPC Memory System | Per-NPC ChromaDB vector memory. Emotion state machine. Relationship scores. Personality-driven dialogue. | ✅ Done |
| 4 | Dynamic Narrative Engine | Consequence propagation. Story arc generator (setup→climax→resolution). Plot thread tracker. Bartle profiling. | ✅ Done |
| 5 | Player Behavior Predictor | Markov chain next-action prediction. Engagement scorer. Frustration detector. Skill assessor. Content pre-generation. | ✅ Done |
| 6 | Multi-Player Sync | WebSocket connection manager. Room-based broadcasts. World snapshot on connect. Real-time player movement sync. | ✅ Done |
| 7 | Economy & Faction Sim | Autonomous faction agents. 25+ action types. Supply/demand pricing (21 commodities). APScheduler every 15 min. | ✅ Done |
| 8 | Combat & Skill Resolution | d20 dice engine. Turn-based combat with status effects. Skill checks. Social interactions. LLM narration. | ✅ Done |
| 9 | GM Agent System | 5 LangGraph agents: Narrator + Content Director + NPC Orchestrator + Conflict Resolver + Continuity. Proactive GM tick. | ✅ Done |

---

### Stage 1: World State Engine

The foundation of everything. A relational database that models a living game world as interconnected entities.

**What you built:**
- 10 SQLAlchemy entity models: World, Region, Location, NPC, Player, Faction, Quest, Item, WorldEvent, PlayerAction, FactionRelationship
- World clock system: 1 real hour = 1 world day. Seasons, time of day, year tracking all calculated automatically from elapsed real time.
- LLM-powered world builder: generates 4 regions, 3 factions, starting city + tavern + market + dungeon, 6 NPCs with Big Five personalities, 2 starter quests.
- 13 REST API endpoints covering all world state operations.

**Why it matters:**  
Every other stage reads from and writes to this database. Without Stage 1, nothing else works. The world clock is what makes NPCs have schedules, seasons affect economy prices, and time actually pass while players are offline.

**Key technical concept:**  
The NPC entity stores Big Five personality traits (openness, conscientiousness, extraversion, agreeableness, neuroticism) as float columns. These numbers control how every NPC speaks, reacts, and behaves across all future stages.

---

### Stage 2: Procedural World Generator

The world generates itself dynamically. No two runs produce the same content.

**What you built:**
- Name generator: culturally consistent names for human, elven, dwarven, coastal, dark themes. Same seed always produces same name (deterministic).
- World context injection: before any LLM call, the full world state (factions, wars, events, economy) is injected into the prompt. All generated content is consistent with current world reality.
- Location generator: biome-aware. Forest locations get bandits and druids. Mountain locations get dwarven architecture and ore veins. Desert locations get ancient tombs.
- Complete dungeon generator: 3 floors with enemies + hazards + treasures, a boss with lore, and a legendary final item.
- Autonomous world tick: events generate themselves without player input. Factions fight, markets shift, disasters occur.

**Key technical concept:**  
World Context Injection is what makes procedural generation coherent instead of random. The LLM does not make things up in isolation. It generates content that follows the internal logic of this specific world at this specific moment.

---

### Stage 3: NPC Memory & Personality System

Every NPC remembers every interaction with every player permanently across sessions. This is the stage that makes the world feel genuinely alive.

**What you built:**
- Per-NPC ChromaDB collections: `npc_{id}_memory`. Each NPC has their own isolated vector store.
- Semantic memory retrieval: memories are found by meaning, not keyword matching. "You helped me" and "you saved my life" both surface when the player mentions helping.
- Emotion state machine: 20+ action types each change NPC emotion. Player helped = grateful. Player stole = angry. Emotions decay over time at a rate modified by agreeableness.
- Relationship scoring: -1.0 (mortal enemy, attacks on sight) to +1.0 (devoted ally, fights alongside). Eight relationship tiers each unlock different behaviors.
- Personality-driven dialogue: the same memory produces completely different dialogue depending on Big Five traits. High extraversion talks more. Low agreeableness holds grudges longer.

**The magic moment:**  
Talk to an NPC, help them, come back later and say "remember me?" The NPC retrieves your shared history from ChromaDB and responds with genuine recognition. This is the most impressive demo in the entire project.

---

### Stage 4: Dynamic Narrative Engine

Player choices ripple through the world for weeks of game time. The world has memory and consequences.

**What you built:**
- Consequence engine: player kills merchant → immediate (market closes), short-term (family mourns, faction investigates), long-term (bounty placed, rival merchant expands). All generated from current world context.
- Story arc generator: complete 3-act structure. Setup → Rising Action → Climax → 3 possible resolutions based on player choices.
- Arc stage machine: arcs advance automatically over time via the narrative tick. If player ignores the climax, the world auto-resolves with the worst outcome.
- Plot thread tracker: multiple simultaneous storylines tracked with connection mapping. When two threads intersect the system records the link.
- Player profiler: Bartle type classification (explorer, achiever, socializer, killer) from action history.

**Why this is different from Projects 1 and 2:**  
Projects 1 and 2 were reactive systems. They answered questions. Stage 4 is a proactive system. The world has its own agenda and moves forward without the player. Consequences the player caused weeks ago are still unfolding.

---

### Stage 5: Player Behavior Predictor

The system predicts what the player will do next and generates content before they ask for it. Zero wait time.

**What you built:**
- Markov chain predictor: personal transition matrix per player. Starts from prior probabilities (40%) and blends with actual player data (60%). More playtime = more accurate predictions.
- Engagement scorer: measures actions per hour, variety, and streak length. Score 0–10 with content-type breakdown showing which content generates the most follow-up actions.
- Frustration detector: 5 signal types. Repeated actions (stuck), frequency drop (bored), aggressive escalation (frustrated), aimless wandering (lost). Each signal has specific intervention suggestions.
- Skill assessor: 5 dimensions (quest completion, combat effectiveness, discovery rate, action diversity, decision speed). Produces novice/beginner/intermediate/advanced/expert rating with difficulty recommendations.
- Pre-generation pipeline: if predictor says player will move to a new location, that location is generated before the player decides to go there.

---

### Stage 6: Multi-Player World Synchronization

Multiple players exist simultaneously in the same world. Their actions are visible to each other in real time.

**What you built:**
- ConnectionManager: tracks all WebSocket connections by `world_id` and `player_id`. Supports world-wide broadcasts, location-specific broadcasts, and direct player messages.
- World snapshot on connect: when a player connects, they immediately receive the complete current world state (location, NPCs, online players, recent events, active quests).
- Room-based events: player enters location → all players at that location see the arrival message. Player leaves → departure broadcast. Player does something notable → world-wide broadcast.
- Message protocol: send `{action: move|chat|action|ping, data: {...}}` receive JSON response + other players receive relevant broadcasts.

**The two-tab test:**  
Open two browser tabs. Connect both as different players. When Player 2 connects, Player 1 instantly receives a "Player 2 has entered the world" message without refreshing. This is real-time multiplayer.

---

### Stage 7: Economy & Faction Simulation

The world runs autonomously every 15 minutes. Factions make decisions, markets shift, wars start and end without any player involvement.

**What you built:**
- Faction agent system: each faction evaluates situation → selects from 25+ action types based on faction type priorities → applies resource changes → generates event. Kingdoms prioritize military. Guilds prioritize wealth. Cults prioritize influence.
- Faction relation drift: every tick, relation scores drift based on faction type conflicts and resource competition. Relations shift from neutral → hostile → at_war organically.
- Supply/demand economy: 21 commodities with base prices. War active → weapons spike +80%, luxury goods drop 40%. Winter → food prices spike 150%. Plague → herbs triple. All automatic.
- APScheduler: starts automatically when server launches. Runs full tick every 15 minutes: faction turns + relation updates + economy recalculation + narrative advancement + WebSocket broadcasts.
- Player trading: buy/sell at current market prices. Smart players buy weapons before predicted wars, sell during the price spike.

---

### Stage 8: Combat & Skill Resolution Engine

Every action has a mechanically-determined outcome with vivid LLM-generated narration.

**What you built:**
- Dice engine: d4/d6/d8/d12/d20 with advantage (roll twice take higher) and disadvantage (roll twice take lower). Critical hits (natural 20) deal double damage dice.
- Turn-based combat: initiative roll determines order. Both sides roll to hit and deal damage. 10 status effects (stunned, bleeding, poisoned, frightened, inspired, burning, enraged, slowed, shielded, blinded) applied on critical hits.
- 6 enemy templates: bandit/guard/wolf/skeleton/mage/troll each with unique HP, weapon, armor, flee threshold, and loot table.
- Skill resolver: 20+ skills mapped to player stats. Lock-picking uses stealth. Climbing uses strength. Persuasion uses charisma. Difficulty classes from trivial (DC 5) to nearly impossible (DC 25).
- Social resolver: persuade/intimidate/deceive/inspire/bribe. Each type uses different stats, affects relationship score differently, triggers different NPC emotions. Connects directly to Stage 3 NPC memory.
- LLM combat narrator: converts mechanical results (11 damage, MISS, CRITICAL HIT) into vivid 2–4 sentence descriptions of the specific blow, sound, sensation, and momentum shift.

---

### Stage 9: Game Master Agent System

Five specialized AI agents act as an autonomous Game Master, reading the entire world state and generating coherent, personalized responses to every player trigger.

**The 5 agents:**

1. **World Narrator Agent:** converts raw location data into vivid atmospheric prose. Knows time of day, season, which NPCs are present, their emotions, other players at the location, recent events. Generates suggested player actions.
2. **Content Director Agent:** reads player behavior prediction (Stage 5), active story arcs (Stage 4), available quests, engagement score. Plans what content to generate next. Explorer players get discovery hooks. Killers get combat encounters. Frustrated players get rescue NPCs.
3. **NPC Orchestrator Agent:** checks all NPCs at location using Stage 3 relationship scores and memory counts. Decides which NPCs approach the player proactively. Grateful NPCs want to reward. Hostile NPCs want to confront. Quest givers who have never met the player approach first.
4. **Conflict Resolver Agent:** detects multi-party conflicts (two hostile NPCs, competing faction interests, moral dilemma). Generates 3 resolution options with different skill requirements, faction implications, and consequences.
5. **World Continuity Agent:** fact-checks all other agents' outputs against real world state. Catches "scene says thriving but economy shows war depression." Approves or sends specific agent back for revision. Max 2 revision loops.

**What makes this the most powerful stage:**  
Every previous stage is a data source for Stage 9. The GM reads Stage 1 (world facts), Stage 2 (generated content), Stage 3 (NPC memories), Stage 4 (story arcs), Stage 5 (player prediction), Stage 6 (online players), Stage 7 (economy state), Stage 8 (combat history). The GM response is the synthesis of all 8 stages into a single coherent game experience.

---

## 3. Remaining Stages to Build (10–12)

Three stages remain. Each one dramatically increases the power and polish of the platform.

---

### Stage 10: Procedural Quest Generator

| Problem it solves | What you will build |
|---|---|
| Right now quests are hand-written. A world with millions of players needs infinite unique quests that feel personal and connected to the current world state. A player who built reputation with merchants should get different quests than one who betrayed them. | A quest generator that reads player history, world state, active arcs, and faction relations to produce quests that are unique to this player at this moment in this world. |

**New files to create:**
- `backend/quest_generator/quest_template.py` — quest type definitions (fetch, kill, escort, investigate, diplomatic, craft, explore, rescue)
- `backend/quest_generator/quest_personalizer.py` — reads player profile + world state to select appropriate quest type and difficulty
- `backend/quest_generator/quest_builder.py` — LLM generates full quest: title, description, objectives, NPC dialogue, rewards, failure consequences
- `backend/quest_generator/quest_chain.py` — links quests into chains. Completing quest A unlocks B which unlocks C. Chains adapt based on how A was completed.
- `backend/quest_generator/quest_pipeline.py` — orchestrates generation + personalisation + database save + NPC assignment

**Quest types explained:**

| Type | Description | Best For |
|---|---|---|
| Fetch / Deliver | Retrieve item from location and bring to NPC. Item has lore connecting it to world events. | Achievers, new players |
| Kill / Clear | Eliminate enemy presence. Enemy type reflects current faction conflicts. | Killers, combat focused |
| Escort | Protect an NPC on a journey. NPC has personality and reacts to events. | Socializers, protectors |
| Investigate | Find information about a mystery. Clues lead to deeper world secrets. | Explorers, detectives |
| Diplomatic | Negotiate between two factions. Outcome shifts faction relations. | Socializers, politicians |
| Exploration | Discover and map a new location. Rewards lore and rare items. | Explorers, collectors |
| Rescue | Save a captured NPC. Creates strong relationship with rescued NPC. | All types |

**How quest generation works step by step:**

1. Player profile loaded: Bartle type (Stage 4), skill level (Stage 5), faction reputations (Stage 1)
2. World state read: active wars (Stage 7), story arcs (Stage 4), available NPCs at location (Stage 1)
3. Quest type selected: Explorer gets investigation quest. Achiever gets clear dungeon quest. Type matches player.
4. LLM generates content: objective text, NPC dialogue lines, reward description. All connected to world events.
5. Quest saved to database and assigned to a specific NPC who becomes the quest giver.
6. NPC stores quest assignment as a memory. Will approach player using Stage 3 system.

**New endpoints:**
- `POST /quest/generate/{player_id}` — generate personalized quest for player
- `POST /quest/generate-chain/{player_id}` — generate 3-quest chain
- `GET /quest/active/{player_id}` — get player active quests
- `POST /quest/complete/{quest_id}` — complete quest + generate follow-up
- `GET /quest/available/{location_id}` — all quests at a location

**New concepts you will learn:**
- Quest state machines: `HIDDEN → AVAILABLE → ACTIVE → COMPLETED/FAILED/EXPIRED`
- Dynamic objective tracking: objectives update based on player actions automatically
- Branching quest design: completing an objective in different ways opens different follow-up paths
- Quest expiry: quests that have time pressure auto-fail after N world-days

---

### Stage 11: World Memory & Lore Engine (GraphRAG)

| Problem it solves | What you will build |
|---|---|
| The world generates thousands of events, NPCs, quests, and consequences. There is no way to search or reason across this history. A player who asks "what happened to the merchant I met 3 weeks ago?" gets no answer. | GraphRAG over world history. A knowledge graph where every entity is a node and every event is an edge. Query it with natural language and get answers connected across the full world timeline. |

**What is GraphRAG?**  
GraphRAG = Graph + RAG (Retrieval Augmented Generation). Instead of searching a flat list of documents, you search a knowledge graph where every piece of information is connected to related pieces. A query about a merchant surfaces the merchant entity, their death event, their wife's grief event, the resulting price change, and the bounty placed on the killer — all in one query because they are connected by edges in the graph.

**New files to create:**
- `backend/world_lore/lore_graph.py` — NetworkX graph with world entities as nodes, events as edges
- `backend/world_lore/lore_indexer.py` — converts all world events into graph nodes/edges automatically
- `backend/world_lore/lore_embedder.py` — embeds each node/edge for semantic search with ChromaDB
- `backend/world_lore/lore_retriever.py` — hybrid retrieval: graph traversal + vector search
- `backend/world_lore/lore_synthesizer.py` — LLM synthesizes retrieved graph paths into coherent lore answers
- `backend/world_lore/lore_pipeline.py` — orchestrates full GraphRAG query pipeline

**Graph structure:**

| Element | Types | Example |
|---|---|---|
| Nodes (entities) | Player, NPC, Location, Faction, Quest, Item, Event | "Aldric the Merchant" node with name, role, location |
| Edges (relations) | killed_by, loved_by, occurred_at, caused_by, part_of | Aldric → killed_by → Player Thoshanth |
| Node embeddings | Semantic vectors of entity description | Find similar entities by meaning |
| Edge weights | Importance score of relationship | Murder edges weight higher than conversation edges |
| Temporal data | World day timestamp on every edge | Query "what happened to Aldric after day 5?" |

**How a GraphRAG lore query works:**

1. Player asks: "What happened to the merchant who lived in the market?"
2. Embed query → find most similar node embeddings in ChromaDB → retrieve Aldric node
3. Graph traversal from Aldric node: follow all connected edges within 3 hops
4. Retrieved subgraph: Aldric → killed_by → Player, Aldric → mourned_by → Mara, Aldric → shop_sold_to → Shadow Conclave
5. LLM synthesizes path into narrative: "Aldric was murdered in the market. His wife Mara mourned for weeks before selling the shop to a mysterious buyer later revealed to be the Shadow Conclave..."

**New endpoints:**
- `POST /lore/query` — natural language lore question answered from graph
- `GET /lore/entity/{entity_type}/{entity_id}` — full history of any entity
- `GET /lore/timeline/{world_id}` — chronological world history
- `POST /lore/index` — rebuild lore graph from all world events
- `GET /lore/connections/{entity_id}` — all entities connected to this entity

**New concepts you will learn:**
- GraphRAG vs standard RAG: flat retrieval vs graph traversal. GraphRAG finds connected information that flat search misses.
- Knowledge graph construction: how to turn event logs into a graph with meaningful relationships
- Multi-hop reasoning: following chains of relationships to answer complex questions
- Temporal graph queries: filtering graph traversal by time windows

---

### Stage 12: Full Stack Game Interface

| Problem it solves | What you will build |
|---|---|
| The entire game runs through raw API calls in Swagger UI. Non-technical players cannot use it. Without a proper game interface, this is an engineering demo, not a game. | A full React game interface with real-time world map, dialogue panel, inventory, quest log, market, and live multiplayer events. This is the stage that turns an API into a game. |

**UI Panels to build:**
- **World Map Panel:** SVG canvas showing all regions and locations. Player avatar moves between locations. Other players shown as different colored dots. Location danger level shown by color.
- **Scene Panel:** GM narrator output displayed here. NPC reactions shown below scene text. Suggested actions appear as clickable buttons.
- **Dialogue Panel:** talk to any NPC. Full conversation history shown. NPC's emotion and relationship score shown with colored indicator. Memory count shown.
- **Quest Log Panel:** all active, completed, and failed quests. Objectives with checkboxes. Rewards shown. Quest giver NPC linked.
- **Inventory & Market Panel:** player inventory on left. Location market on right. Buy/sell at current prices. Price trend indicators (up/down arrows).
- **Combat Panel:** when combat starts, switches to turn-based combat view. HP bars, status effects, round log, narration. Action buttons: attack, flee, use item.
- **World Events Feed:** real-time sidebar showing world events via WebSocket. Faction wars, player actions, economy shifts. Color-coded by severity.
- **Faction Status Panel:** all factions, their resources, current relations (visual relationship web), and recent actions.

**Frontend structure:**
- `frontend/src/pages/GamePage.js` — main game view with panel layout
- `frontend/src/components/WorldMap.js` — SVG world map with clickable locations
- `frontend/src/components/SceneView.js` — GM narrator + NPC reactions + action buttons
- `frontend/src/components/DialogueBox.js` — NPC conversation interface
- `frontend/src/components/CombatView.js` — turn-based combat UI
- `frontend/src/components/QuestLog.js` — quest tracker
- `frontend/src/components/Inventory.js` — player items and market
- `frontend/src/components/EventsFeed.js` — real-time WebSocket event sidebar
- `frontend/src/hooks/useWebSocket.js` — WebSocket connection management hook
- `frontend/src/hooks/useGameState.js` — central game state with React context

**Key technical challenge: real-time state management**  
Multiple WebSocket events arrive simultaneously. A world event fires while the player is in combat while an NPC wants to speak. React state must handle all of these without losing any. Solution: event queue with priority system. Combat events highest priority, world events lowest.

**New concepts you will learn:**
- SVG canvas programming: drawing maps, positioning entities, handling clicks on a coordinate system
- React WebSocket integration: persistent connection, reconnection logic, event routing
- Game state management: complex nested state across many panels that must stay in sync
- Real-time UI updates: new events appearing without any user interaction or refresh
- React Context API: sharing game state between deeply nested components without prop drilling

**New endpoints needed for Stage 12:**
- `GET /world/{id}/map-data` — all locations with coordinates for SVG map rendering
- `POST /player/action` — unified action endpoint the frontend uses for all player actions
- `GET /player/{id}/full-state` — complete player state for initial load
- `POST /gm/scene/{location_id}` — get scene when clicking on map location

---

## 4. Deployment Plan

After Stage 12 the platform is ready to deploy.

### 4.1 Docker Setup

**Dockerfile (backend):**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p game_data chroma_db logs
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml:**
```yaml
version: "3.9"
services:
  backend:
    build: .
    ports: ["8000:8000"]
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    volumes:
      - ./game_data:/app/game_data
      - ./chroma_db:/app/chroma_db
  frontend:
    build: ./frontend
    ports: ["3000:80"]
    depends_on: [backend]
```

**Run locally:**
```bash
docker compose up --build
```

---

### 4.2 Cloud Deployment — Railway (Recommended)

Railway is the easiest deployment platform for this stack. Free tier available. Automatic HTTPS. Supports WebSockets natively.

1. Create account at railway.app
2. Connect GitHub repository
3. Add environment variable: `OPENROUTER_API_KEY`
4. Set start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Railway detects Dockerfile automatically and builds
6. WebSocket connections work on Railway without extra configuration

---

### 4.3 Cloud Deployment — Render

1. Create account at render.com
2. New Web Service → connect GitHub repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variable: `OPENROUTER_API_KEY`
6. For WebSockets: enable "WebSocket Support" in advanced settings

---

### 4.4 VPS Deployment — DigitalOcean / Linode

Full control. Best for production with real users. Costs $6–12/month for a basic droplet.

1. Create Ubuntu 22.04 droplet (minimum 2GB RAM for ChromaDB + embedder)
2. SSH in. Install Docker: `apt install docker.io docker-compose`
3. Clone your GitHub repo: `git clone https://github.com/yourusername/ai-game-master`
4. Create `.env` file with `OPENROUTER_API_KEY`
5. Run: `docker compose up -d` (detached mode, runs in background)
6. Configure Nginx as reverse proxy for HTTPS + WebSocket upgrade
7. Get free SSL certificate: `certbot --nginx`

**Nginx config for WebSocket support:**
```nginx
location /ws/ {
    proxy_pass http://localhost:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

---

## 5. How All 12 Stages Connect

Every stage feeds into every other stage. This is what separates this project from a collection of features.

### 5.1 The Data Flow Diagram

When a player enters a location, here is the exact chain of stage calls:

```
Player clicks location on map (Stage 12 frontend)
  → POST /gm/describe-scene (Stage 9 GM System)
      → Stage 1: get_location_context()    ← SQLite world database
      → Stage 1: get_current_world_time()  ← World clock calculation
      → Stage 6: get_players_at_location() ← WebSocket connection manager
      → Stage 3: get_npc_relationship()    ← ChromaDB per-NPC memory
      → Stage 5: full_player_prediction()  ← Markov chain + engagement
      → Stage 4: get_active_arcs()         ← Story arc JSON files
      → Stage 7: get_current_prices()      ← Economy modifier calculation
      → LLM: generates vivid scene description
      → Stage 6: broadcast to other players at location
  ← Returns: scene text + NPC reactions + suggested actions + quest hooks
```

---

### 5.2 The Technology Stack Summary

| Layer | Technology | Used In Stage |
|---|---|---|
| API Framework | FastAPI + Uvicorn | All stages |
| Database | SQLite + SQLAlchemy | Stages 1–9 (world state) |
| Vector DB | ChromaDB | Stage 3 (NPC memory), Stage 11 (lore) |
| Embeddings | sentence-transformers MiniLM | Stage 3, Stage 11 |
| Agent Framework | LangGraph | Stage 4 (narrative), Stage 9 (GM) |
| LLM | NVIDIA Nemotron 120B via OpenRouter | All generation stages |
| Scheduling | APScheduler | Stage 7 (faction/economy sim) |
| Real-time | WebSockets (FastAPI) | Stage 6 (multiplayer) |
| Knowledge Graph | NetworkX | Stage 11 (GraphRAG lore) |
| Frontend | React + SVG Canvas | Stage 12 |
| Containerization | Docker + docker-compose | Deployment |

---

## 6. Git Branch Strategy

Every stage follows the same branching pattern. Never commit directly to main.

```
main (always stable — deployable)
  └── phase1 (integration branch)
        ├── stage-1/world-state-engine   ✔ merged
        ├── stage-2/procedural-generator  ✔ merged
        ├── stage-3/npc-memory            ✔ merged
        ├── stage-4/narrative-engine      ✔ merged
        ├── stage-5/player-behavior       ✔ merged
        ├── stage-6/multiplayer-sync      ✔ merged
        ├── stage-7/economy-simulation    ✔ merged
        ├── stage-8/combat-resolution     ✔ merged
        ├── stage-9/game-master-agents   ✔ merged
        ├── stage-10/quest-generator     ← BUILD NEXT
        ├── stage-11/world-lore-graphrag  ← after 10
        └── stage-12/full-stack-game-ui   ← final stage
```

**For each new stage:**

1. `git checkout phase1`
2. `git checkout -b stage-10/quest-generator`
3. Build the stage, test all endpoints
4. `git add . && git commit -m "stage-10: procedural quest generator"`
5. In GitHub Desktop: merge to phase1
6. Create next stage branch from phase1

---

## 7. Portfolio Value & Career Impact

### 7.1 Skills Demonstrated Across All 3 Projects

| Skill Category | Specific Technologies & Patterns |
|---|---|
| LLM Integration | OpenRouter, NVIDIA Nemotron, fallback chains, prompt engineering, JSON extraction, temperature control |
| RAG Systems | ChromaDB, PubMedBERT, hybrid retrieval (semantic + BM25 + metadata), LlamaIndex, RAGAS evaluation |
| Agent Systems | LangGraph, multi-agent coordination, shared state, conditional routing, revision loops, tool use |
| Vector Databases | ChromaDB per-entity collections, semantic search, cosine similarity, embedding strategies |
| Knowledge Graphs | NetworkX, graph traversal (BFS), causal chain tracking, GraphRAG hybrid retrieval |
| Real-time Systems | FastAPI WebSockets, connection management, room broadcasting, state synchronization |
| Autonomous Systems | APScheduler, agent-based simulation, autonomous decision trees, world ticks |
| Backend Development | FastAPI, SQLAlchemy, SQLite, REST API design, async/await, middleware |
| Frontend Development | React, WebSocket hooks, real-time UI, SVG canvas, state management |
| DevOps | Docker, docker-compose, Nginx, environment management, cloud deployment |
| ML Concepts | Markov chains, classification, Bartle typology, engagement scoring, frustration detection |

---

### 7.2 Job Roles This Portfolio Targets

- **AI Engineer** — primary target. You have built exactly what AI Engineers build: LLM integration, RAG systems, agent pipelines, evaluation frameworks.
- **ML Engineer** — secondary target. Markov chains, Bartle classification, RAGAS evaluation, QLoRA fine-tuning demonstrated.
- **Game AI Engineer** — specialised target. Project 3 specifically. Very few people have built autonomous game worlds with NPC memory. High demand at EA, Ubisoft, Riot, Epic.
- **Full Stack AI Engineer** — Projects 1+2+3 together demonstrate end-to-end: database → LLM pipeline → agent system → React frontend → deployment.

---

### 7.3 What Makes This Portfolio Unique

- Three complete projects across three completely different domains (research, medical, gaming).
- Every stage is production-grade with proper logging, error handling, fallback chains, and structured output.
- The Game Master Engine is genuinely novel — no open-source project does autonomous NPC memory + economy simulation + procedural generation + multiplayer sync + LangGraph GM agents in one system.
- Medical platform demonstrates safety-first AI engineering: 6-layer guardrails, emergency detection, HIPAA-aware PII handling, hallucination detection. This is what healthcare AI companies need.
- All three projects are on GitHub with detailed READMEs, stage-by-stage commit history, and documented architecture.

---

*AI Engineering Learning Roadmap • M.S.N. Thoshanth Reddy • HITAM Hyderabad • 2026*
