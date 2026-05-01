import React, { useState } from 'react';
import './LoreQuery.css';

function LoreQuery({ worldId }) {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleQuery = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    try {
      setLoading(true);
      const response = await fetch('/lore/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          world_id: worldId,
          query: query,
          max_results: 10,
          max_hops: 2,
        })
      });
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Failed to query lore:', error);
      alert('Failed to query lore');
    } finally {
      setLoading(false);
    }
  };

  const exampleQueries = [
    "What happened in this world?",
    "Who are the important NPCs?",
    "What quests are available?",
    "Tell me about recent events",
    "What factions exist?",
  ];

  return (
    <div className="lore-query">
      <div className="lore-header">
        <h2>📚 World Lore</h2>
        <p>Ask questions about the world's history and events</p>
      </div>

      <form onSubmit={handleQuery} className="query-form card">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask about the world... (e.g., 'What happened to the merchant?')"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? 'Searching...' : '🔍 Search'}
        </button>
      </form>

      <div className="example-queries">
        <p>Example queries:</p>
        <div className="examples-list">
          {exampleQueries.map((ex, idx) => (
            <button
              key={idx}
              className="example-btn"
              onClick={() => setQuery(ex)}
              disabled={loading}
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {result && (
        <div className="lore-result">
          <div className="answer-card card">
            <h3>Answer</h3>
            <p className="answer-text">{result.answer}</p>
          </div>

          {result.sources && (
            <div className="sources-section">
              {result.sources.top_entities && result.sources.top_entities.length > 0 && (
                <div className="sources-card card">
                  <h4>🎭 Related Entities</h4>
                  <div className="entities-list">
                    {result.sources.top_entities.map((entity, idx) => (
                      <div key={idx} className="entity-item">
                        <span className="entity-name">{entity.name}</span>
                        <span className="entity-type">{entity.type}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.sources.key_events && result.sources.key_events.length > 0 && (
                <div className="sources-card card">
                  <h4>📰 Key Events</h4>
                  <ul className="events-list">
                    {result.sources.key_events.map((event, idx) => (
                      <li key={idx}>{event}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="sources-stats">
                <span>Nodes found: {result.sources.nodes_found}</span>
                <span>Edges found: {result.sources.edges_found}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default LoreQuery;
