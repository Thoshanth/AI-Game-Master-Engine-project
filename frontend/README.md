# AI Game Master Engine - Frontend

React-based game interface for the AI Game Master Engine.

## Features

- **Scene View**: Explore locations, see NPCs, and generate quests
- **Quest Log**: Track active quests and complete them
- **Lore Query**: Ask natural language questions about world history
- **World Info**: View world statistics, factions, and recent events

## Setup

### Install Dependencies

```bash
cd frontend
npm install
```

### Start Development Server

```bash
npm start
```

The app will open at http://localhost:3000

### Build for Production

```bash
npm run build
```

## Configuration

The frontend proxies API requests to `http://localhost:8000` (configured in `package.json`).

Make sure the backend server is running before starting the frontend.

## Components

- **GamePage**: Main game interface with tabs
- **SceneView**: Location exploration and NPC interaction
- **QuestLog**: Quest management and completion
- **LoreQuery**: GraphRAG-powered lore queries
- **WorldInfo**: World statistics and faction information

## Styling

All components use CSS modules with a dark fantasy theme:
- Primary color: #667eea (purple)
- Background: #1a1a2e (dark blue)
- Cards: #2d3748 (gray)

## API Integration

The frontend communicates with the backend REST API:
- `/player/{id}/context` - Player data
- `/location/{id}/context` - Location data
- `/quest/generate/{player_id}` - Generate quests
- `/quest/active/{player_id}` - Get active quests
- `/quest/complete/{quest_id}` - Complete quests
- `/lore/query` - Query world lore
- `/world/{id}` - World information
- `/world/{id}/factions` - Faction data
- `/world/{id}/events` - Recent events

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Development

### File Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── SceneView.js/css
│   │   ├── QuestLog.js/css
│   │   ├── LoreQuery.js/css
│   │   └── WorldInfo.js/css
│   ├── pages/
│   │   └── GamePage.js/css
│   ├── styles/
│   │   ├── index.css
│   │   └── App.css
│   ├── App.js
│   └── index.js
└── package.json
```

### Adding New Features

1. Create component in `src/components/`
2. Add corresponding CSS file
3. Import and use in `GamePage.js`
4. Add new tab if needed

## Troubleshooting

### Cannot connect to backend

- Ensure backend is running on port 8000
- Check proxy configuration in `package.json`

### Styling issues

- Clear browser cache
- Check CSS import statements
- Verify class names match CSS files

### API errors

- Check browser console for error messages
- Verify backend endpoints are working
- Check network tab in browser dev tools
