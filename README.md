# GameZZ — Chess & Battleship Web App

Play chess or battleship with friends in a web browser.

## Features

- Chess over the web — move input, SVG board, spectators
- Battleship ("Sea Battle") over the web — click-to-place fleets, turn-based shooting
- Invite links for joining games (creator gets a link, friend joins as second player)
- Multilingual (English, Russian)
- Games auto-expire after 24 hours
- SQLite storage
- Shared game framework (`core/game_framework.py`) — easy to add more one-on-one games

## Quick Start with Docker

```bash
docker compose up -d
```

- **Web app**: http://localhost:8000

## Local Development (no Docker)

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the web app
uvicorn web.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000 — the app works immediately.

## How to Play

### Chess

1. Open http://localhost:8000
2. Click **Create New Game**
3. Share the invite link with a friend
4. Friend opens the link and clicks **Join as Black**
5. Take turns typing moves (e.g. `e2e4`, `Nf3`, `O-O`)
6. Click **↻ Refresh** to see the latest board

### Battleship

1. Open http://localhost:8000/battleship
2. Click **Create New Game**
3. Share the invite link with a friend
4. Friend opens the link and joins as Player B
5. Both players place their 10-ship fleet on a 10×10 grid (click a cell, use **Rotate** to flip orientation), then **Lock Fleet**
6. Once both fleets are locked, take turns shooting the enemy board — a hit lets you shoot again
7. Sink all enemy ships to win

## Project Structure

```
chess_bot/
├── core/                        # Shared logic
│   ├── game_framework.py        # Generic session/join/expiry layer for web games
│   ├── game_manager.py          # ChessGameManager (extends framework)
│   ├── battleship.py            # Pure battleship rules engine
│   ├── battleship_manager.py    # BattleshipManager (extends framework)
│   └── constants.py
├── web/                         # FastAPI web app
│   ├── main.py                  # Routes (chess + battleship)
│   ├── templates/               # Jinja2 HTML templates
│   └── static/                  # CSS, battleship.js
├── configuration.py             # App version, paths
├── requirements.txt
├── docker-compose.yaml
└── Dockerfile
```

## Releasing

The version lives in `configuration.py` (`APP_VERSION`, `major.minor.patch`).
Bump the **patch** digit before each deploy. See the local opencode skill
`chess-bot-deploy` for the full dev → deploy chain.
