import React, { useState } from 'react';
import GamePage from './pages/GamePage';
import './styles/App.css';

function App() {
  const [worldId, setWorldId] = useState(1);
  const [playerId, setPlayerId] = useState(1);

  return (
    <div className="App">
      <header className="app-header">
        <h1>🎮 AI Game Master Engine</h1>
        <div className="header-info">
          <span>World: {worldId}</span>
          <span>Player: {playerId}</span>
        </div>
      </header>
      
      <GamePage worldId={worldId} playerId={playerId} />
    </div>
  );
}

export default App;
