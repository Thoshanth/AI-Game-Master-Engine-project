import React, { useState, useEffect } from 'react';
import './SceneView.css';

function SceneView({ worldId, playerId, locationId }) {
  const [scene, setScene] = useState(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadScene();
  }, [locationId]);

  const loadScene = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/location/${locationId}/context?world_id=${worldId}&player_id=${playerId}`);
      const data = await response.json();
      setScene(data);
    } catch (error) {
      console.error('Failed to load scene:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateQuest = async () => {
    try {
      setGenerating(true);
      const response = await fetch(`/quest/generate/${playerId}?world_id=${worldId}&location_id=${locationId}`, {
        method: 'POST'
      });
      const quest = await response.json();
      alert(`New Quest Generated: ${quest.title}\n\n${quest.description}`);
      loadScene(); // Reload to show new quest
    } catch (error) {
      console.error('Failed to generate quest:', error);
      alert('Failed to generate quest');
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="scene-view loading">
        <div className="spinner"></div>
      </div>
    );
  }

  if (!scene) {
    return <div className="scene-view">No scene data available</div>;
  }

  return (
    <div className="scene-view">
      <div className="scene-header">
        <h2>{scene.location.name}</h2>
        <span className="location-type">{scene.location.type}</span>
      </div>

      <div className="scene-description card">
        <p>{scene.location.description}</p>
      </div>

      <div className="scene-details">
        <div className="detail-card card">
          <h4>📊 Location Stats</h4>
          <div className="stats-grid">
            <div>
              <span>Population:</span>
              <strong>{scene.location.population}</strong>
            </div>
            <div>
              <span>Wealth:</span>
              <strong>{scene.location.wealth_level}/10</strong>
            </div>
            <div>
              <span>Safety:</span>
              <strong>{scene.location.safety_level}/10</strong>
            </div>
          </div>
        </div>

        {scene.npcs_present && scene.npcs_present.length > 0 && (
          <div className="npcs-card card">
            <h4>👥 NPCs Present ({scene.npcs_present.length})</h4>
            <div className="npc-list">
              {scene.npcs_present.map(npc => (
                <div key={npc.id} className="npc-item">
                  <div className="npc-info">
                    <strong>{npc.name}</strong>
                    <span className="npc-role">{npc.role}</span>
                  </div>
                  <div className="npc-status">
                    <span className={`emotion ${npc.emotion}`}>{npc.emotion}</span>
                    <span className="activity">{npc.current_activity}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {scene.available_quests > 0 && (
          <div className="quests-available card">
            <h4>📜 Available Quests</h4>
            <p>{scene.available_quests} quest(s) available at this location</p>
            <button onClick={generateQuest} disabled={generating}>
              {generating ? 'Generating...' : '✨ Generate New Quest'}
            </button>
          </div>
        )}

        {scene.recent_events && scene.recent_events.length > 0 && (
          <div className="recent-events card">
            <h4>📰 Recent Events</h4>
            <div className="events-list">
              {scene.recent_events.map((event, idx) => (
                <div key={idx} className="event-item">
                  <strong>{event.title}</strong>
                  <p>{event.description}</p>
                  <span className="event-day">Day {Math.floor(event.world_day)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="scene-actions">
        <button onClick={loadScene}>🔄 Refresh Scene</button>
        <button onClick={generateQuest} disabled={generating}>
          {generating ? 'Generating...' : '✨ Generate Quest'}
        </button>
      </div>
    </div>
  );
}

export default SceneView;
