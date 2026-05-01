# 🎮 AI Game Master Engine

A complete AI-powered game master system that creates living, breathing RPG worlds with autonomous NPCs, dynamic narratives, and intelligent quest generation.

## 🌟 Features

### 🤖 AI-Powered Systems
- **LLM Content Generation**: Procedurally generated locations, NPCs, quests, and dialogue
- **5-Agent GM System**: Coordinated AI agents manage storytelling, content, NPCs, conflicts, and continuity
- **GraphRAG Lore Engine**: Natural language queries over world history with multi-hop reasoning
- **Player Behavior Prediction**: Markov chain prediction with content pre-generation

### 🌍 Living World
- **Autonomous Simulation**: Factions make decisions, economy shifts, NPCs follow schedules
- **Dynamic Economy**: Supply/demand pricing for 21 commodities
- **Faction Politics**: 25+ autonomous action types, relation drift, wars
- **Consequence Propagation**: Actions have immediate, short-term, and long-term effects

### 👥 NPC Intelligence
- **Vector Memory**: Per-NPC ChromaDB memory with semantic retrieval
- **Personality System**: Big Five traits drive dialogue and behavior
- **Emotion Engine**: 20+ action types affect NPC emotions
- **Relationship Tracking**: -1.0 to +1.0 relationship scores with 8 tiers

### 📜 Quest System
- **12 Quest Types**: Fetch, deliver, kill, investigate, diplomatic, and more
- **Player Personalization**: Quests match Bartle type (explorer, achiever, socializer, killer)
- **Quest Chains**: Multi-quest storylines with branching paths
- **Dynamic Difficulty**: Scales from novice to expert based on skill assessment

### ⚔️ Combat & Skills
- **d20 Dice Engine**: Advantage/disadvantage, critical hits
- **Turn-Based Combat**: 10 status effects, 6 enemy templates
- **Skill Resolution**: 20+ skills with difficulty classes
- **Social Interactions**: Persuade, intimidate, deceive, inspire, bribe

### 🎭 Narrative Engine
- **Story Arcs**: 3-act structure with multiple resolutions
- **Plot Tracking**: Multiple simultaneous storylines
- **Player Profiling**: Bartle type classification from behavior
- **Adaptive Content**: World responds to player choices

## 🏗️ Architecture

### Backend (Python)
- **Framework**: FastAPI + Uvicorn
- **Database**: SQLite + SQLAlchemy (13 tables)
- **Vector DB**: ChromaDB for embeddings
- **Graph**: NetworkX for knowledge graph
- **LLM**: NVIDIA Nemotron 120B via OpenRouter
- **Agents**: LangGraph for multi-agent coordination
- **Real-time**: WebSockets for multiplayer
- **Scheduling**: APScheduler for autonomous simulation

### Frontend (React)
- **Framework**: React 18
- **Components**: 4 main views (Scene, Quests, Lore, World)
- **Styling**: CSS Modules with dark fantasy theme
- **HTTP**: Axios for API calls

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 14+
- OpenRouter API key

### 1. Clone Repository
```bash
git clone <repository-url>
cd AI-Game-Master-Engine-project
```

### 2. Backend Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "OPENROUTER_API_KEY=your_key_here" > .env

# Start server
uvicorn backend.main:app --reload
```

Server runs at: http://localhost:8000

### 3. Frontend Setup
```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

Frontend runs at: http://localhost:3000

### 4. Create Your First World
```bash
# Create world
curl -X POST "http://localhost:8000/world/create?name=Eldoria&theme=dark%20fantasy"

# Create player
curl -X POST "http://localhost:8000/player/create?world_id=1&username=hero&character_name=Hero&character_class=warrior"

# Build lore index
curl -X POST "http://localhost:8000/lore/build/1"
```

### 5. Play!
Open http://localhost:3000 in your browser

## 📚 Documentation

- **API Documentation**: http://localhost:8000/docs (when server running)
- **Project Overview**: [PROJECT_COMPLETE.md](PROJECT_COMPLETE.md)
- **Quick Reference**: [FINAL_SUMMARY.md](FINAL_SUMMARY.md)
- **Understanding Guide**: [understanding_game.md](understanding_game.md)

### Stage-Specific Documentation
- **Stage 10 (Quests)**: [backend/quest_generator/README.md](backend/quest_generator/README.md)
- **Stage 11 (Lore)**: [backend/world_lore/README.md](backend/world_lore/README.md)
- **Stage 12 (Frontend)**: [frontend/README.md](frontend/README.md)

## 🎯 12 Stages

| Stage | Name | Status |
|-------|------|--------|
| 1 | World State Engine | ✅ Complete |
| 2 | Procedural World Generator | ✅ Complete |
| 3 | NPC Memory & Personality | ✅ Complete |
| 4 | Dynamic Narrative Engine | ✅ Complete |
| 5 | Player Behavior Predictor | ✅ Complete |
| 6 | Multi-Player Synchronization | ✅ Complete |
| 7 | Economy & Faction Simulation | ✅ Complete |
| 8 | Combat & Skill Resolution | ✅ Complete |
| 9 | GM Agent System | ✅ Complete |
| 10 | Procedural Quest Generator | ✅ Complete |
| 11 | World Memory & Lore (GraphRAG) | ✅ Complete |
| 12 | Full Stack Game Interface | ✅ Complete |

## 🧪 Testing

### Backend Tests
```bash
# Test quest generator
python test_quest_generator.py

# Test lore engine
python test_lore_engine.py
```

### Frontend Testing
1. Open http://localhost:3000
2. Navigate through all 4 tabs
3. Generate a quest in Scene view
4. Complete a quest in Quest Log
5. Query lore in Lore view
6. View world info in World view

## 📊 API Endpoints

### World Management (Stage 1)
- `POST /world/create` - Create new world
- `GET /world/{id}` - Get world summary
- `GET /world/{id}/time` - Get world time
- `GET /world/{id}/regions` - Get regions
- `GET /world/{id}/factions` - Get factions
- `GET /world/{id}/events` - Get events

### Procedural Generation (Stage 2)
- `POST /generate/location` - Generate location
- `POST /generate/dungeon` - Generate dungeon
- `POST /generate/npc` - Generate NPC
- `POST /generate/item` - Generate item

### NPC Memory (Stage 3)
- `POST /npc/{id}/interact` - Interact with NPC
- `GET /npc/{id}/memory/{player_id}` - Get NPC memories
- `GET /npc/{id}/relationship/{player_id}` - Get relationship

### Narrative (Stage 4)
- `POST /narrative/consequence` - Trigger consequences
- `GET /narrative/arcs/{world_id}` - Get story arcs
- `POST /narrative/arc/generate` - Generate arc
- `GET /narrative/player/{player_id}/profile` - Get player profile

### Prediction (Stage 5)
- `GET /predict/next-action/{player_id}` - Predict next actions
- `GET /predict/engagement/{player_id}` - Get engagement score
- `GET /predict/frustration/{player_id}` - Detect frustration
- `GET /predict/skill/{player_id}` - Assess skill

### Multiplayer (Stage 6)
- `WebSocket /ws/{world_id}/{player_id}` - Real-time connection

### Economy & Factions (Stage 7)
- `GET /economy/prices/{world_id}` - Get current prices
- `POST /economy/trade` - Process trade
- `GET /faction/{id}/turn` - Run faction turn
- `POST /simulation/start/{world_id}` - Start simulation

### Combat (Stage 8)
- `POST /combat/start` - Start combat
- `POST /combat/{id}/round` - Resolve round
- `POST /skill/attempt` - Attempt skill check
- `POST /social/interact` - Social interaction

### GM System (Stage 9)
- `POST /gm/trigger` - Trigger GM system
- `POST /gm/describe-scene` - Describe scene
- `POST /gm/handle-action` - Handle player action
- `POST /gm/tick/{world_id}` - Proactive GM tick

### Quest Generator (Stage 10)
- `POST /quest/generate/{player_id}` - Generate quest
- `POST /quest/generate-chain/{player_id}` - Generate quest chain
- `GET /quest/active/{player_id}` - Get active quests
- `POST /quest/complete/{quest_id}` - Complete quest
- `GET /quest/types` - Get quest types

### Lore Engine (Stage 11)
- `POST /lore/build/{world_id}` - Build lore index
- `POST /lore/query` - Query lore
- `GET /lore/entity/{type}/{name}` - Get entity history
- `GET /lore/connections/{type}/{name}` - Get connections
- `GET /lore/timeline` - Get timeline
- `POST /lore/rebuild/{world_id}` - Rebuild index

## 🎮 Example Gameplay

### 1. Explore a Location
```bash
curl "http://localhost:8000/location/1/context?world_id=1&player_id=1"
```

### 2. Generate a Quest
```bash
curl -X POST "http://localhost:8000/quest/generate/1?world_id=1&location_id=1"
```

### 3. Interact with NPC
```bash
curl -X POST "http://localhost:8000/npc/1/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "player_id": 1,
    "player_message": "Hello!",
    "action_type": "player_questioned",
    "world_id": 1
  }'
```

### 4. Query World Lore
```bash
curl -X POST "http://localhost:8000/lore/query" \
  -H "Content-Type: application/json" \
  -d '{
    "world_id": 1,
    "query": "What happened in this world?"
  }'
```

### 5. Complete a Quest
```bash
curl -X POST "http://localhost:8000/quest/complete/1?player_id=1&world_id=1&completion_method=diplomatic"
```

## 🐳 Docker Deployment

### Using Docker Compose
```bash
docker-compose up --build
```

### Manual Docker Build
```bash
# Build backend
docker build -t ai-game-master-backend .

# Run backend
docker run -p 8000:8000 -e OPENROUTER_API_KEY=your_key ai-game-master-backend
```

## ☁️ Cloud Deployment

### Railway (Recommended)
1. Connect GitHub repository
2. Add `OPENROUTER_API_KEY` environment variable
3. Deploy automatically

### Render
1. Create new Web Service
2. Connect repository
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Add `OPENROUTER_API_KEY` environment variable

### DigitalOcean/Linode VPS
1. Create Ubuntu 22.04 droplet (2GB RAM minimum)
2. Install Docker: `apt install docker.io docker-compose`
3. Clone repository
4. Create `.env` with API key
5. Run: `docker-compose up -d`

## 🔧 Configuration

### Environment Variables
```bash
# Required
OPENROUTER_API_KEY=your_key_here

# Optional
DATABASE_URL=sqlite:///./game_world.db
CHROMA_DB_PATH=./chroma_db
LOG_LEVEL=INFO
```

### World Clock
- Default: 1 real hour = 1 world day
- Configurable in world creation

### Simulation Interval
- Default: Every 15 minutes
- Configurable in `simulation_runner.py`

## 📈 Performance

- **Backend startup**: ~2 seconds
- **World creation**: ~30 seconds (LLM generation)
- **Quest generation**: ~2-3 seconds
- **Lore query**: ~2-3 seconds
- **Lore index build**: ~5-10 seconds (100 entities)
- **Combat round**: <100ms
- **API response**: <200ms average

## 🛠️ Technology Stack

### Backend
- FastAPI 0.104+
- SQLAlchemy 2.0+
- ChromaDB 0.4+
- NetworkX 3.1+
- LangGraph 0.0.40+
- APScheduler 3.10+
- sentence-transformers 2.2+

### Frontend
- React 18.2+
- Axios 1.6+
- React Scripts 5.0+

### AI/ML
- NVIDIA Nemotron 120B (via OpenRouter)
- MiniLM embeddings
- Markov chain prediction

## 🤝 Contributing

This is a portfolio project. Feel free to fork and extend!

## 📝 License

See [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**M.S.N. Thoshanth Reddy**
- Institution: B.Tech | HITAM, Hyderabad
- Project: AI Engineering Roadmap • Project 3
- Date: May 2026

## 🙏 Acknowledgments

- OpenRouter for LLM API access
- ChromaDB for vector storage
- NetworkX for graph algorithms
- FastAPI for excellent API framework
- React team for frontend framework

## 📞 Support

For issues or questions:
1. Check documentation in `/docs`
2. Review API docs at http://localhost:8000/docs
3. Check logs in `/logs` directory

## 🎯 Future Enhancements

- Voice interface (speech-to-text)
- Procedural music generation
- Advanced tactical combat
- Crafting system
- Player housing
- Guild system
- PvP combat
- Mobile app

---

**Status**: ✅ Production Ready

**Version**: 1.0.0

**Last Updated**: May 2026

🎮 **The AI Game Master Engine is complete and ready to play!** ✨
