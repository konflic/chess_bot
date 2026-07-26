# CheZZ — Telegram Chess Bot + Web App

Play chess with friends via Telegram or a web browser.

## Features

- Multiplayer chess over Telegram or Web
- Play against the computer
- Invite links for joining games
- Board rendered as SVG/PNG
- Multilingual (English, Russian)
- Games auto-expire after 24 hours (web)
- SQLite storage

## Quick Start with Docker

```bash
# Start both Telegram bot and web app
docker compose up -d

# Or start only one service:
docker compose up -d bot    # Telegram bot only
docker compose up -d web    # Web app only
```

- **Web app**: http://localhost:8000
- **Telegram bot**: talk to `@chezz_game_bot` on Telegram

## Local Development (no Docker)

You can run the **web app alone** without a Telegram token — only the bot requires it.

### 1. Set up

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the web app

```bash
uvicorn web.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000 — the web app works immediately. No Telegram token needed.

### 3. Run the Telegram bot (optional)

```bash
echo "YOUR_BOT_TOKEN_HERE" > TOKEN
python bot.py
```

### 4. After pulling new changes

```bash
pip install -r requirements.txt  # install any new dependencies
# No DB migrations needed — tables are created/updated automatically on startup
```

## How to Play (Web)

1. Open http://localhost:8000
2. Click **Create New Game**
3. Share the invite link with a friend
4. Friend opens the link and clicks **Join as Black**
5. Take turns typing moves (e.g. `e2e4`, `Nf3`, `O-O`)
6. Click **↻ Refresh** to see the latest board

## Commands (Telegram)

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | All commands |
| `/newgame` | Create a new game |
| `/playvs` | Play against computer |
| `/status` | Show current active game |
| `/board` | Show board image |
| `/ping` | Remind opponent it's their turn |
| `/surrender` | Surrender current game |

## Project Structure

```
chess_bot/
├── core/              # Shared logic (engine, game manager, constants)
├── bot/               # Telegram bot (uses core/)
├── web/               # FastAPI web app (uses core/)
│   ├── main.py        # Routes
│   ├── templates/     # Jinja2 HTML templates
│   └── static/        # CSS
├── configuration.py   # Bot name, version, paths
├── languages.py       # Translations
├── docker-compose.yaml
└── Dockerfile
```
