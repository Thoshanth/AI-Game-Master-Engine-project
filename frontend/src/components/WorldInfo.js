import React, { useState, useEffect } from 'react';
import './WorldInfo.css';

function WorldInfo({ worldId }) {
  const [worldData, setWorldData] = useState(null);
  const [factions, setFactions] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadWorldData();
  }, [worldId]);

  const loadWorldData = async () => {
    try {
      setLoading(true);
      
      // Load world summary
      const worldResponse = await fetch(`/world/${worldId}`);
      const worldData = await worldResponse.json();
      setWorldData(worldData);

      // Load factions
      const factionsResponse = await fetch(`/world/${worldId}/factions`);
      const factionsData = await factionsResponse.json();
      setFactions(factionsData);

      // Load recent events
      const eventsResponse = await fetch(`/world/${worldId}/events?limit=10`);
      const eventsData = await eventsResponse.json();
      setEvents(eventsData);

    } catch (error) {
      console.error('Failed to load world data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="world-info loading">
        <div className="spinner"></div>
      </div>
    );
  }

  if (!worldData) {
    return <div className="world-info">Failed to load world data</div>;
  }

  return (
    <div className="world-info">
      <div className="world-header">
        <h2>🌍 {worldData.name}</h2>
        <p>{worldData.description}</p>
      </div>

      <div className="world-stats card">
        <h3>World Statistics</h3>
        <div className="stats-grid">
          <div className="stat-item">
            <span className="stat-label">Regions</span>
            <span className="stat-value">{worldData.total_regions}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Locations</span>
            <span className="stat-value">{worldData.total_locations}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">NPCs</span>
            <span className="stat-value">{worldData.total_npcs}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Factions</span>
            <span className="stat-value">{worldData.total_factions}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Players</span>
            <span className="stat-value">{worldData.total_players}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Quests</span>
            <span className="stat-value">{worldData.total_quests}</span>
          </div>
        </div>
      </div>

      {factions.length > 0 && (
        <div className="factions-section">
          <h3>⚔️ Factions</h3>
          <div className="factions-grid">
            {factions.map(faction => (
              <div key={faction.id} className="faction-card card">
                <div className="faction-header">
                  <h4>{faction.name}</h4>
                  <span className="faction-type">{faction.type}</span>
                </div>
                <p className="faction-description">{faction.description}</p>
                {faction.motto && (
                  <p className="faction-motto">"{faction.motto}"</p>
                )}
                <div className="faction-stats">
                  <div>
                    <span>💰</span>
                    <span>{faction.wealth}</span>
                  </div>
                  <div>
                    <span>⚔️</span>
                    <span>{faction.military_strength}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {events.length > 0 && (
        <div className="events-section">
          <h3>📰 Recent Events</h3>
          <div className="events-timeline">
            {events.map(event => (
              <div key={event.id} className="event-card card">
                <div className="event-header">
                  <h4>{event.title}</h4>
                  <span className="event-day">Day {Math.floor(event.world_day)}</span>
                </div>
                <p>{event.description}</p>
                <div className="event-meta">
                  <span className={`event-type ${event.type}`}>{event.type}</span>
                  {event.is_notable && <span className="notable-badge">Notable</span>}
                  <span className="importance">Importance: {event.importance}/10</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="world-actions">
        <button onClick={loadWorldData}>🔄 Refresh</button>
      </div>
    </div>
  );
}

export default WorldInfo;
