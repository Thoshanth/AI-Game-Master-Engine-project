"""
Stage 11: World Memory & Lore Engine (GraphRAG)

GraphRAG = Graph + RAG (Retrieval Augmented Generation)

Creates a queryable knowledge graph where:
- Every entity (NPC, location, faction, quest, item) is a node
- Every event (death, trade, quest, war) is an edge
- Natural language queries traverse the graph
- Multi-hop reasoning connects related information

Example query:
"What happened to the merchant I met 3 weeks ago?"

GraphRAG finds:
- Merchant entity node
- Death event edge
- Killer player node
- Mourning wife node
- Shop sale event edge
- Shadow Conclave buyer node

Returns: "The merchant was killed. His wife mourned for weeks 
before selling the shop to the Shadow Conclave..."
"""
