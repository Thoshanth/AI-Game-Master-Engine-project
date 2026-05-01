import React, { useState, useEffect } from 'react';
import './QuestLog.css';

function QuestLog({ worldId, playerId }) {
  const [quests, setQuests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedQuest, setSelectedQuest] = useState(null);

  useEffect(() => {
    loadQuests();
  }, [worldId, playerId]);

  const loadQuests = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/quest/active/${playerId}?world_id=${worldId}`);
      const data = await response.json();
      setQuests(data.quests || []);
    } catch (error) {
      console.error('Failed to load quests:', error);
    } finally {
      setLoading(false);
    }
  };

  const completeQuest = async (questId) => {
    if (!window.confirm('Mark this quest as completed?')) return;

    try {
      const response = await fetch(`/quest/complete/${questId}?player_id=${playerId}&world_id=${worldId}&completion_method=standard`, {
        method: 'POST'
      });
      const result = await response.json();
      alert(`Quest Completed!\n\nRewards:\n- Gold: ${result.rewards_granted.gold}\n- XP: ${result.rewards_granted.experience}`);
      loadQuests();
      setSelectedQuest(null);
    } catch (error) {
      console.error('Failed to complete quest:', error);
      alert('Failed to complete quest');
    }
  };

  if (loading) {
    return (
      <div className="quest-log loading">
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="quest-log">
      <div className="quest-log-header">
        <h2>📜 Quest Log</h2>
        <span className="quest-count">{quests.length} Active</span>
      </div>

      {quests.length === 0 ? (
        <div className="no-quests card">
          <p>No active quests</p>
          <p className="hint">Visit locations to find new quests!</p>
        </div>
      ) : (
        <div className="quests-container">
          <div className="quests-list">
            {quests.map(quest => (
              <div 
                key={quest.id} 
                className={`quest-item card ${selectedQuest?.id === quest.id ? 'selected' : ''}`}
                onClick={() => setSelectedQuest(quest)}
              >
                <div className="quest-header">
                  <h3>{quest.title}</h3>
                  <span className={`quest-type ${quest.type}`}>{quest.type}</span>
                </div>
                <p className="quest-description">{quest.description}</p>
                <div className="quest-meta">
                  <span className={`quest-state ${quest.state}`}>{quest.state}</span>
                  {quest.expires_at && (
                    <span className="quest-expires">
                      Expires: Day {Math.floor(quest.expires_at)}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {selectedQuest && (
            <div className="quest-details card">
              <h3>{selectedQuest.title}</h3>
              <p className="quest-description">{selectedQuest.description}</p>

              <div className="quest-section">
                <h4>📋 Objectives</h4>
                <ul className="objectives-list">
                  {selectedQuest.objectives.map((obj, idx) => (
                    <li key={idx}>{obj}</li>
                  ))}
                </ul>
              </div>

              <div className="quest-section">
                <h4>🎁 Rewards</h4>
                <div className="rewards-grid">
                  {selectedQuest.rewards.gold && (
                    <div className="reward-item">
                      <span>💰 Gold</span>
                      <strong>{selectedQuest.rewards.gold}</strong>
                    </div>
                  )}
                  {selectedQuest.rewards.experience && (
                    <div className="reward-item">
                      <span>⭐ Experience</span>
                      <strong>{selectedQuest.rewards.experience}</strong>
                    </div>
                  )}
                </div>
              </div>

              <div className="quest-actions">
                <button 
                  className="complete-btn"
                  onClick={() => completeQuest(selectedQuest.id)}
                >
                  ✅ Complete Quest
                </button>
                <button 
                  className="close-btn"
                  onClick={() => setSelectedQuest(null)}
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default QuestLog;
