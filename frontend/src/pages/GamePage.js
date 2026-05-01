import React, { useState, useEffect } from 'react';
import SceneView from '../components/SceneView';
import QuestLog from '../components/QuestLog';
import LoreQuery from '../components/LoreQuery';
import WorldInfo from '../components/WorldInfo';
import './GamePage.css';

function GamePage({ worldId, playerId }) {
  const [activeTab, setActiveTab] = useState('scene');
  const [playerContext, setPlayerContext] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPlayerContext();
  }, [worldId, playerId]);

  const loadPlayerContext = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/player/${playerId}/context?world_id=${worldId}`);
      const data = await response.json();
      setPlayerContext(data);
    } catch (error) {
      console.error('Failed to load player context:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="game-page loading">
        <div className="spinner"></div>
        <p>Loading game world...</p>
      </div>
    );
  }

  if (!playerContext) {
    return (
      <div className="game-page error">
        <h2>Failed to load game</h2>
        <p>Please check that the world and player exist.</p>
        <button onClick={loadPlayerContext}>Retry</button>
      </div>
    );
  }

  return (
    <div className="game-page">
      <div className="game-sidebar">
        <div className="player-card card">
          <h3>{playerContext.player.character_name}</h3>
          <div className="player-stats">
            <div className="stat">
              <span className="stat-label">Level</span>
              <span className="stat-value">{playerContext.player.level}</span>
            </div>
            <div className="stat">
              <span className="stat-label">HP</span>
              <span className="stat-value">
                {playerContext.player.health}/{playerContext.player.max_health}
              </span>
            </div>
            <div className="stat">
              <span className="stat-label">Gold</span>
              <span className="stat-value">{playerContext.player.gold}</span>
            </div>
            <div className="stat">
              <span className="stat-label">XP</span>
              <span className="stat-value">{playerContext.player.experience}</span>
            </div>
          </div>
          <div className="player-location">
            <strong>Location:</strong> {playerContext.current_location.name}
          </div>
        </div>

        <div className="world-time card">
          <h4>World Time</h4>
          <div className="time-info">
            <div>Day {Math.floor(playerContext.world_time.total_days)}</div>
            <div>{playerContext.world_time.time_of_day}</div>
            <div>{playerContext.world_time.season}</div>
          </div>
        </div>
      </div>

      <div className="game-main">
        <div className="tab-navigation">
          <button 
            className={activeTab === 'scene' ? 'active' : ''}
            onClick={() => setActiveTab('scene')}
          >
            🎭 Scene
          </button>
          <button 
            className={activeTab === 'quests' ? 'active' : ''}
            onClick={() => setActiveTab('quests')}
          >
            📜 Quests
          </button>
          <button 
            className={activeTab === 'lore' ? 'active' : ''}
            onClick={() => setActiveTab('lore')}
          >
            📚 Lore
          </button>
          <button 
            className={activeTab === 'world' ? 'active' : ''}
            onClick={() => setActiveTab('world')}
          >
            🌍 World
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'scene' && (
            <SceneView 
              worldId={worldId} 
              playerId={playerId}
              locationId={playerContext.current_location.id}
            />
          )}
          {activeTab === 'quests' && (
            <QuestLog 
              worldId={worldId} 
              playerId={playerId}
            />
          )}
          {activeTab === 'lore' && (
            <LoreQuery worldId={worldId} />
          )}
          {activeTab === 'world' && (
            <WorldInfo worldId={worldId} />
          )}
        </div>
      </div>
    </div>
  );
}

export default GamePage;
