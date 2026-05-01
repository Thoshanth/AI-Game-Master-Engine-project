# Stage 11: World Memory & Lore Engine (GraphRAG)

## Overview

Stage 11 implements **GraphRAG** (Graph + Retrieval Augmented Generation) to create a queryable knowledge graph of all world history. Players can ask natural language questions like "What happened to the merchant I met 3 weeks ago?" and get accurate, connected answers.

## What is GraphRAG?

GraphRAG combines:
1. **Knowledge Graph**: Entities (nodes) connected by relationships (edges)
2. **Vector Search**: Semantic similarity search over graph elements
3. **Graph Traversal**: Following connections to find related information
4. **LLM Synthesis**: Converting graph data into natural language

### Traditional RAG vs GraphRAG

| Traditional RAG | GraphRAG |
|-----------------|----------|
| Flat document search | Connected entity graph |
| Finds similar documents | Finds related entities + connections |
| No relationship awareness | Explicit relationships |
| Single-hop retrieval | Multi-hop reasoning |

## Architecture

```
lore_pipeline.py (Orchestrator)
    ↓
lore_graph.py (Knowledge Graph)
    ├─> NetworkX MultiDiGraph
    ├─> Nodes: NPCs, Players, Locations, Factions, Quests, Items
    └─> Edges: Events, Relationships, Actions
    ↓
lore_embedder.py (Vector Search)
    ├─> ChromaDB for embeddings
    ├─> Semantic search over nodes/edges
    └─> Time-range filtering
    ↓
lore_retriever.py (Hybrid Retrieval)
    ├─> Vector search for seed nodes
    ├─> Graph traversal for connections
    ├─> Path finding between entities
    └─> Temporal filtering
    ↓
lore_synthesizer.py (LLM Synthesis)
    └─> Natural language answers
```

## Key Features

### 1. Knowledge Graph Construction

Every entity in the world becomes a node:
- **NPCs**: Name, role, personality, alive status
- **Players**: Character name, class, level
- **Locations**: Name, type, description
- **Factions**: Name, type, goals
- **Quests**: Title, type, state
- **Items**: Name, rarity, properties

Every event becomes an edge:
- **World Events**: Deaths, wars, discoveries
- **Player Actions**: Trades, kills, quests
- **Relationships**: Loves, hates, member_of
- **Locations**: located_at, occurred_at

### 2. Semantic Search

All nodes and edges are embedded as text:
```
"NPC: Aldric. Aldric, a merchant. A kind-hearted trader who..."
"Event: Player killed Aldric. The merchant was murdered in the market..."
```

ChromaDB enables semantic search:
- "merchant" finds Aldric even if query says "trader"
- "killed" finds death events even if query says "murdered"

### 3. Graph Traversal

Multi-hop reasoning finds connections:

```
Query: "What happened to Aldric?"

Step 1: Find Aldric node (vector search)
Step 2: Traverse edges:
  - Aldric → killed_by → Player
  - Aldric → mourned_by → Mara (wife)
  - Aldric → shop_sold_to → Shadow Conclave
Step 3: Synthesize: "Aldric was killed. His wife Mara mourned..."
```

### 4. Temporal Queries

Filter by time range:
```
"What happened between day 5 and day 10?"
"What events occurred in the first week?"
```

### 5. Entity History

Complete timeline for any entity:
```
GET /lore/entity/npc/Aldric

Returns:
- Day 0.0: Aldric created at market
- Day 2.3: Player traded with Aldric
- Day 5.1: Aldric killed by Player
- Day 5.2: Mara mourned Aldric
- Day 7.0: Shop sold to Shadow Conclave
```

### 6. Relationship Mapping

All connections for an entity:
```
GET /lore/connections/npc/Aldric

Returns:
- loves → Mara (wife)
- member_of → Merchant Guild
- located_at → Market Square
- killed_by → Player Thoshanth
```

## API Endpoints

### Build Lore Index

```http
POST /lore/build/{world_id}?force_rebuild=false
```

Builds the knowledge graph from world state. Should be called:
- After world creation
- Periodically (every hour)
- Before running queries

**Response:**
```json
{
  "world_id": 1,
  "status": "success",
  "stats": {
    "graph": {
      "nodes": 156,
      "edges": 423
    },
    "embeddings": {
      "total_documents": 579
    }
  }
}
```

### Query Lore

```http
POST /lore/query
```

**Parameters:**
- `world_id`: World ID
- `query`: Natural language question
- `max_results`: Number of entities to retrieve (default: 10)
- `max_hops`: Graph hops to traverse (default: 2)
- `start_day`: Optional time range start
- `end_day`: Optional time range end

**Example Queries:**
- "What happened to the merchant I met 3 weeks ago?"
- "Who killed Aldric and why?"
- "What is the Shadow Conclave planning?"
- "Tell me about the war between the kingdoms"
- "What quests are connected to the bandit attacks?"

**Response:**
```json
{
  "query": "What happened to Aldric?",
  "answer": "Aldric, a merchant at the market, was killed by the player Thoshanth on day 5.1. His wife Mara mourned his death for several days before selling their shop to the Shadow Conclave on day 7.0.",
  "sources": {
    "nodes_found": 8,
    "edges_found": 12,
    "top_entities": [
      {"name": "Aldric", "type": "npc"},
      {"name": "Mara", "type": "npc"},
      {"name": "Shadow Conclave", "type": "faction"}
    ],
    "key_events": [
      "Player killed Aldric in the market",
      "Mara mourned for weeks",
      "Shop sold to mysterious buyer"
    ]
  }
}
```

### Get Entity History

```http
GET /lore/entity/{entity_type}/{entity_name}?world_id=1&include_narrative=true
```

**Parameters:**
- `entity_type`: npc, player, location, faction, quest, item
- `entity_name`: Name of entity
- `include_narrative`: Generate narrative summary (default: true)

**Response:**
```json
{
  "found": true,
  "entity": {
    "node_id": "npc_5",
    "type": "npc",
    "name": "Aldric",
    "description": "A kind-hearted merchant...",
    "importance": 7.5
  },
  "total_events": 8,
  "timeline": [
    {
      "world_day": 0.0,
      "description": "Aldric created at market",
      "relation": "created"
    },
    {
      "world_day": 5.1,
      "description": "Player killed Aldric",
      "relation": "death"
    }
  ],
  "narrative": "Aldric was a beloved merchant who ran a shop in the market square. He was known for his fair prices and kind demeanor. Tragically, he was killed by an adventurer on day 5, leaving his wife Mara devastated. His shop was later sold to the Shadow Conclave under mysterious circumstances."
}
```

### Get Entity Connections

```http
GET /lore/connections/{entity_type}/{entity_name}?world_id=1&relation_type=loves
```

**Parameters:**
- `entity_type`: Type of entity
- `entity_name`: Name of entity
- `relation_type`: Optional filter (loves, hates, member_of, etc.)
- `include_explanation`: Generate explanation (default: true)

**Response:**
```json
{
  "found": true,
  "entity": {
    "type": "npc",
    "name": "Aldric"
  },
  "total_connections": 6,
  "connections": [
    {
      "target": {"type": "npc", "name": "Mara"},
      "relation": "loves",
      "description": "Aldric loves Mara"
    },
    {
      "target": {"type": "faction", "name": "Merchant Guild"},
      "relation": "member_of",
      "description": "Aldric is a member of this faction"
    }
  ],
  "explanation": "Aldric had deep connections to the market community. He was married to Mara, whom he loved dearly. As a member of the Merchant Guild, he maintained strong professional relationships with other traders. His shop was located in the market square, where he was a familiar face to many travelers."
}
```

### Get Timeline

```http
GET /lore/timeline?world_id=1&start_day=0&end_day=7&include_narrative=true
```

**Parameters:**
- `start_day`: Start of period (world days)
- `end_day`: End of period (world days)
- `event_types`: Optional comma-separated list
- `include_narrative`: Generate narrative (default: true)

**Response:**
```json
{
  "start_day": 0.0,
  "end_day": 7.0,
  "total_events": 23,
  "events": [
    {
      "world_day": 0.0,
      "relation": "created",
      "description": "World created",
      "source": {"type": "world", "name": "Eldoria"},
      "importance": 10.0
    },
    {
      "world_day": 5.1,
      "relation": "death",
      "description": "Player killed Aldric",
      "source": {"type": "player", "name": "Thoshanth"},
      "target": {"type": "npc", "name": "Aldric"},
      "importance": 8.0
    }
  ],
  "narrative": "The first week of Eldoria's history was marked by both creation and tragedy. The world came into being on day 0, with four regions and three factions establishing themselves. By day 5, the first major conflict occurred when the adventurer Thoshanth killed the merchant Aldric in the market square, sending shockwaves through the community. Aldric's widow Mara mourned for days before making the difficult decision to sell their shop to the Shadow Conclave on day 7."
}
```

### Rebuild Index

```http
POST /lore/rebuild/{world_id}
```

Force rebuilds the entire index. Use when:
- Major world changes occurred
- Graph seems out of sync
- Testing/debugging

### Get Stats

```http
GET /lore/stats/{world_id}
```

Returns graph statistics:
```json
{
  "world_id": 1,
  "graph": {
    "nodes": 156,
    "edges": 423
  },
  "embeddings": {
    "world_id": 1,
    "collection_name": "world_lore_1",
    "total_documents": 579
  },
  "graph_file_exists": true
}
```

## Integration with Other Stages

### Stage 1: World State Engine
- Reads all entities from database
- Converts to graph nodes
- Stores graph persistently

### Stage 3: NPC Memory System
- NPC relationships become graph edges
- Memory events become temporal edges
- Emotion states tracked in node attributes

### Stage 4: Dynamic Narrative Engine
- Story arcs become quest chains in graph
- Consequences create new edges
- Plot threads connect entities

### Stage 7: Economy & Faction Simulation
- Faction actions become edges
- Economic events tracked temporally
- Faction relations as weighted edges

### Stage 9: GM Agent System
- GM queries lore for context
- Continuity agent checks graph for consistency
- Content director uses lore for quest hooks

### Stage 10: Quest Generator
- Quests become nodes in graph
- Quest completion creates edges
- Quest chains visible as paths

## Graph Structure

### Node Types

| Type | Attributes | Example |
|------|-----------|---------|
| **NPC** | name, role, personality, is_alive, location_id, faction_id | Aldric (merchant) |
| **Player** | name, username, class, level, location_id | Thoshanth (adventurer) |
| **Location** | name, type, description, region_id | Market Square (market) |
| **Faction** | name, type, description, motto | Merchant Guild (guild) |
| **Quest** | title, type, description, state | The Missing Merchant (investigate) |
| **Item** | name, type, rarity, description | Aldric's Ledger (rare) |

### Edge Types

| Relation | Description | Example |
|----------|-------------|---------|
| **killed_by** | Entity was killed by another | Aldric → killed_by → Player |
| **loves** | Positive relationship | Aldric → loves → Mara |
| **hates** | Negative relationship | Bandit → hates → Guard |
| **member_of** | Faction membership | Aldric → member_of → Merchant Guild |
| **located_at** | Physical location | Aldric → located_at → Market |
| **occurred_at** | Event location | Death → occurred_at → Market |
| **completed_quest** | Quest completion | Player → completed_quest → Quest |
| **faction_allied** | Faction alliance | Guild → faction_allied → Kingdom |
| **faction_at_war** | Faction war | Kingdom → faction_at_war → Cult |

### Importance Scoring

Nodes are scored by importance (1-10):
- **Base importance**: Entity type (players=8, factions=7, NPCs=5)
- **Connection importance**: Number of edges (×0.5, max +5)
- **Event importance**: Involvement in major events (×1.0, max +5)

High-importance nodes appear first in search results.

## Example Queries

### Simple Entity Query

```bash
curl "http://localhost:8000/lore/entity/npc/Aldric?world_id=1"
```

Returns Aldric's complete history.

### Complex Multi-Hop Query

```bash
curl -X POST "http://localhost:8000/lore/query" \
  -H "Content-Type: application/json" \
  -d '{
    "world_id": 1,
    "query": "What happened after Aldric died?",
    "max_hops": 3
  }'
```

GraphRAG finds:
1. Aldric's death event
2. Mara's mourning (1 hop from Aldric)
3. Shop sale (2 hops from Aldric)
4. Shadow Conclave involvement (3 hops from Aldric)

### Temporal Query

```bash
curl -X POST "http://localhost:8000/lore/query" \
  -H "Content-Type: application/json" \
  -d '{
    "world_id": 1,
    "query": "What happened in the first week?",
    "start_day": 0,
    "end_day": 7
  }'
```

Returns only events from days 0-7.

### Relationship Query

```bash
curl "http://localhost:8000/lore/connections/npc/Aldric?world_id=1&relation_type=loves"
```

Returns only "loves" relationships for Aldric.

## Performance

- **Graph building**: ~5-10 seconds for 100 entities
- **Embedding**: ~10-20 seconds for 500 documents
- **Query**: ~2-3 seconds (vector search + graph traversal + LLM)
- **Entity history**: <1 second (graph traversal only)
- **Timeline**: <1 second (temporal filtering)

## Storage

- **Graph file**: `game_data/lore_graphs/world_{id}_graph.json`
- **Embeddings**: `chroma_db/world_lore_{id}/`
- **Size**: ~1MB per 1000 entities

## Limitations

- **Graph size**: Tested up to 10,000 nodes
- **Query complexity**: Max 3 hops recommended
- **Time range**: All time ranges supported
- **Concurrent queries**: Thread-safe via pipeline cache

## Future Enhancements

- **Incremental updates**: Add new events without full rebuild
- **Graph visualization**: Visual graph explorer UI
- **Advanced queries**: Aggregations, statistics, patterns
- **Multi-world queries**: Cross-world lore comparison
- **Lore export**: Export graph to various formats

## Files

- `lore_graph.py`: NetworkX knowledge graph construction
- `lore_embedder.py`: ChromaDB vector search
- `lore_retriever.py`: Hybrid retrieval (vector + graph)
- `lore_synthesizer.py`: LLM answer generation
- `lore_pipeline.py`: Main orchestration
- `__init__.py`: Module initialization

## Dependencies

- **NetworkX**: Graph data structure
- **ChromaDB**: Vector embeddings
- **sentence-transformers**: Text embeddings
- **LLM Client**: NVIDIA Nemotron 120B

## Logging

All lore operations are logged:

```
[world_lore.pipeline] Building lore index | world_id=1
[world_lore.graph] Building lore graph | world_id=1
[world_lore.graph] Added 156 NPC nodes
[world_lore.graph] Added 423 world event edges
[world_lore.graph] Graph built | nodes=156 | edges=423
[world_lore.embedder] Embedding graph | world_id=1
[world_lore.embedder] Embedded 579 items | nodes=156 | edges=423
[world_lore.retriever] Retrieving lore | query='What happened to Aldric?'
[world_lore.synthesizer] Synthesizing answer | query='What happened to Aldric?'
```

## Conclusion

Stage 11 transforms the game world from a collection of disconnected events into a living, queryable history. Players can ask questions about anything that has happened and get accurate, connected answers that show how events and entities relate to each other.

**What makes this special:**
- Natural language queries work like talking to a historian
- Multi-hop reasoning finds connections humans might miss
- Temporal queries show how the world evolved
- Every entity's complete history is preserved
- Relationships are explicit and queryable

**Next Stage**: Stage 12 will add a full React game interface with real-time quest log, interactive world map, NPC dialogue system, and visual lore explorer.
