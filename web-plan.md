# Chess Bot → Web App: Implementation Plan

## Goals
- Add a web interface alongside the existing Telegram bot
- Share core logic (`ChessGameManager`, `ComputerEngine`) between both
- No auth — identity is a unique player link per user per game
- Games auto-expire after 24 hours

## 1. Directory Structure

```
chess_bot/
├── core/                          # Shared logic (Telegram-agnostic)
│   ├── __init__.py
│   ├── constants.py               # COMPUTER_PLAYER, START_FEN
│   ├── engine.py                  # ComputerEngine (moved from chess_bot.py)
│   └── game_manager.py            # ChessGameManager (moved + web methods)
├── bot/
│   ├── chess_bot.py               # Telegram handlers only, imports from core
│   └── bot.py                     # Entry point, unchanged
├── web/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, lifespan, background cleanup
│   ├── templates/
│   │   ├── base.html              # Layout shell (CSS, nav)
│   │   ├── index.html             # "Create New Game" button
│   │   ├── game.html              # Board + move input / observer view
│   │   └── join.html              # "Join as Black" confirmation
│   └── static/
│       └── style.css              # Minimal centered-column CSS (~50 lines)
├── configuration.py               # Unchanged
├── languages.py                    # Unchanged
├── motivational_quotes.py          # Unchanged
├── requirements.txt                # + fastapi, uvicorn, jinja2
├── web-plan.md                     # This file
├── Dockerfile                      # Updated (or docker-compose adds web)
└── docker-compose.yaml             # Add web service
```

## 2. Database — New Tables (bot tables untouched)

```sql
CREATE TABLE web_games (
    game_id TEXT PRIMARY KEY,
    fen TEXT NOT NULL DEFAULT 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    status TEXT NOT NULL DEFAULT 'waiting',  -- waiting | playing | finished
    move_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE web_players (
    player_token TEXT PRIMARY KEY,
    game_id TEXT NOT NULL,
    color TEXT NOT NULL CHECK(color IN ('white', 'black')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES web_games(game_id) ON DELETE CASCADE
);

CREATE TABLE web_moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    move_san TEXT NOT NULL,
    player_token TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES web_games(game_id) ON DELETE CASCADE
);

CREATE TABLE web_join_tokens (
    join_token TEXT PRIMARY KEY,
    game_id TEXT NOT NULL,
    used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES web_games(game_id) ON DELETE CASCADE
);
```

## 3. Token Generation

```python
import secrets, string

def make_game_id() -> str:
    """Short ID for game URLs. 8 chars, lowercase + digits."""
    return ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))

def make_token(length: int = 32) -> str:
    """URL-safe token for player identification."""
    return secrets.token_urlsafe(length)
```

## 4. Route Design

| Method | Route | Behavior |
|--------|-------|----------|
| GET | `/` | Index page — "Create New Game" button |
| POST | `/games/create` | Generate game_id, white_token, join_token; insert rows; redirect → `/game/{id}?player={token}` |
| GET | `/game/{game_id}` | If `?player=` matches a player → player view with move input. Otherwise → observer view (board only, no input) |
| GET | `/game/{game_id}/join?token=` | Show join page if token valid + unused |
| POST | `/game/{game_id}/join` | Mark join_token used, assign black player token, redirect → their game page |
| POST | `/game/{game_id}/move` | Validate player + turn, make move, update FEN, redirect → game page |

## 5. Page Layouts

### Index (`index.html`)
```
┌──────────────────────────────────┐
│          ♟ CheZZ Web             │
│                                  │
│       [ Create New Game ]        │
│                                  │
│   ─── or paste a game link ───   │
│   ┌──────────────────────┐       │
│   │ /game/abc12345?player│       │
│   └──────────────────────┘       │
│   [ Join Game ]                  │
└──────────────────────────────────┘
```

The join-by-link field is optional convenience. Primary flow is share-link click.

### Game (`game.html`) — Player View
```
┌───────────────────────────────┐
│  Game: abc12345  (your turn)  │
├───────────────────────────────┤
│                               │
│      [SVG CHESS BOARD]        │
│                               │
├───────────────────────────────┤
│  Moves: 1. e4  e5             │
│          2. Nf3 Nc6           │
│                               │
│  Your move: ┌─────────┐       │
│             │ e2e4    │ [→]   │
│             └─────────┘       │
│                               │
│  ───────────────────────────  │
│  ⚠ Save this link to play:   │
│  /game/abc12345?player=xyz..  │
└───────────────────────────────┘
```

### Game (`game.html`) — Waiting View
```
┌───────────────────────────────┐
│  Game: abc12345  (opponent's  │
│                turn)          │
├───────────────────────────────┤
│      [SVG CHESS BOARD]        │
├───────────────────────────────┤
│  Moves: 1. e4  e5             │
│          2. Nf3                │
│                               │
│  ⏳ Waiting for opponent...   │
│                               │
│  [ ↻ Refresh ]                │
└───────────────────────────────┘
```

### Game (`game.html`) — Observer View
```
┌───────────────────────────────┐
│  Game: abc12345  (observing)  │
├───────────────────────────────┤
│      [SVG CHESS BOARD]        │
├───────────────────────────────┤
│  Moves: 1. e4  e5             │
│          2. Nf3 Nc6           │
│                               │
│  [ ↻ Refresh ]                │
└───────────────────────────────┘
```

### Join (`join.html`)
```
┌───────────────────────────────┐
│  You were invited to a game!  │
│                               │
│  You will play as Black.      │
│                               │
│   [ Join as Black → ]         │
│                               │
│  Game: abc12345               │
└───────────────────────────────┘
```

## 6. Board Rendering (Web)

For the web, use **inline SVG** directly — no `cairosvg`, no temp files:

```python
import chess.svg

def get_board_svg(fen: str) -> str:
    board = chess.Board(fen)
    return chess.svg.board(board=board, size=400, coordinates=True)
```

The SVG is injected directly into the HTML template via Jinja2 `|safe` filter. No file I/O needed for the web.

(The Telegram bot continues using cairosvg + PNG, unchanged.)

## 7. Background Cleanup

In FastAPI's `lifespan` context manager, spawn an `asyncio` task:

```python
async def cleanup_loop():
    while True:
        await asyncio.sleep(300)  # every 5 minutes
        db.execute("DELETE FROM web_games WHERE expires_at < datetime('now')")
        # CASCADE deletes players, moves, join_tokens
```

## 8. Full Sequence Flow

```
Creator                        Server                        Friend
  │                              │                            │
  ├─ POST /games/create ───────→│                            │
  │                              ├─ gen game_id               │
  │                              ├─ gen white_token(32)       │
  │                              ├─ gen join_token(32)        │
  │                              ├─ INSERT web_games          │
  │                              ├─ INSERT web_players(W)     │
  │                              ├─ INSERT web_join_tokens    │
  │←─ 302 → /game/ID?player=W_token ────────────────────────│
  │                              │                            │
  │  Page shows board + share    │                            │
  │  link at bottom of page.     │                            │
  │  "⚠ Save your player link!"  │                            │
  │                              │                            │
  │───────── share join URL ────────────────────────────────→│
  │                              │                            │
  │                              │  GET /game/ID/join?token=xxx
  │                              │←───────────────────────────│
  │                              ├─ verify token valid+unused │
  │                              ├─ show join confirmation    │
  │                              │── [Join as Black] ────────→│
  │                              │                            │
  │                              │  POST /game/ID/join        │
  │                              │←───────────────────────────│
  │                              ├─ mark join_token used=1    │
  │                              ├─ gen black_token(32)       │
  │                              ├─ INSERT web_players(B)     │
  │                              ├─ UPDATE status='playing'   │
  │                              │── 302 → /game/ID?player=B_token ──→│
  │                              │                            │
  │               Both see updated board                      │
  │←─────────────────────────────┼───────────────────────────→│
  │                              │                            │
  │  POST /game/ID/move          │                            │
  │  (player_token=W, move=e4)   │                            │
  │←─────────────────────────────│                            │
  │  302 → game page (now        │                            │
  │  opponent's turn)            │                            │
  │                              │  POST /game/ID/move        │
  │                              │  (player_token=B, move=e5) │
  │                              │←───────────────────────────│
  │                              │  302 → game page           │
```

## 9. Edge Cases

| Scenario | Handling |
|----------|----------|
| Join link already used | "This invite link has already been used." Show a "Go back" link. |
| Invalid join token | "Invalid invite link." Show a "Go back" link. |
| Game expired (24h+) | "This game has expired." No board rendering. |
| Move when not your turn | Error flashed on page: "It's not your turn." |
| Invalid move notation | Error flashed: "Invalid move: [reason]" |
| Player token doesn't match | Observer view (board + moves, no input, no share link) |
| Lost player URL | No recovery. The warning at creation is the only safety net. |

## 10. Phased Implementation

### Phase A — Core extraction (safe, no visible change)
1. Create `core/__init__.py`, `core/constants.py`
2. Move `ComputerEngine` → `core/engine.py`
3. Move `ChessGameManager` → `core/game_manager.py`
4. Update `bot/chess_bot.py` imports
5. Verify bot still works

### Phase B — Web tables + cleanup
1. Add web table creation to `init_db()` in `core/game_manager.py`
2. Add background cleanup method
3. Run migration manually on existing DB

### Phase C — Web app routes
1. `web/main.py` — FastAPI app, lifespan
2. `templates/base.html` — HTML shell
3. `templates/index.html` — create button
4. `templates/game.html` — board + moves + input (3 variants)
5. `templates/join.html` — join confirmation
6. `style.css` — centered column, minimal

### Phase D — Integration
1. Run both services: `docker compose up bot web`
2. Test end-to-end: create → share → join → move → observe
3. Verify bot still works in parallel

## 11. Docker Deployment

### Docker Compose

Two services share the same image, differentiated by `command`:

```yaml
services:
  bot:
    restart: always
    volumes:
      - ./tmp:/bot/tmp
      - ./data:/bot/data
    build:
      context: .
    command: python bot.py

  web:
    restart: always
    ports:
      - "8000:8000"
    volumes:
      - ./tmp:/bot/tmp
      - ./data:/bot/data
    build:
      context: .
    command: uvicorn web.main:app --host 0.0.0.0 --port 8000
```

### Volumes
- `./data` — SQLite database (shared between bot and web)
- `./tmp` — Temporary files (board PNGs for bot)

### Usage
```bash
# Build and start everything
docker compose up -d

# Start only web (if bot runs elsewhere)
docker compose up -d web

# View logs
docker compose logs -f web
```

### Port
- Web app: `http://localhost:8000`

---

## 12. Shared Game Framework + Battleship (implemented)

The web app was generalized into a small game framework so one-on-one games
share the same matchmaking flow (create → share invite link → second player
joins → play → finish, 24h expiry, spectator access).

- `core/game_framework.py` — `GameManager` base class + shared DB tables
  (`match_sessions`, `match_players`, `match_join_tokens`, `match_events`).
  Subclasses pick `game_type`, `sides`, `initial_state()` and
  `status_after_join` and get session/join/events/cleanup for free.
- `core/game_manager.py` — `ChessGameManager(GameManager)` (game_type `chess`,
  sides white/black). The old chess `web_*` tables are dropped on startup;
  games live only 24h so nothing needs migrating.
- `core/battleship.py` — pure Russian Sea Battle rules (10×10, fleet
  `[4,3,3,2,2,2,1,1,1,1]`, placement validation, shot resolution, sunk/win).
- `core/battleship_manager.py` — `BattleshipManager(GameManager)` with the
  lifecycle `waiting → placing → playing → finished` (both players lock their
  fleets before shooting starts).

### Routes

| Method | Route | Behavior |
|--------|-------|----------|
| GET | `/battleship` | Battleship index — create button |
| POST | `/battleship/create` | Create game, redirect to player page |
| GET | `/battleship/game/{game_id}` | Game page (player or spectator) |
| GET | `/battleship/game/{game_id}/join?token=` | Join confirmation |
| POST | `/battleship/game/{game_id}/join` | Join as Player B → `placing` |
| POST | `/battleship/game/{game_id}/lock` | Validate + store fleet, mark ready; both ready → `playing` |
| POST | `/battleship/game/{game_id}/shoot` | Fire at a cell; hit = shoot again |
| POST | `/battleship/game/{game_id}/resign` | Resign |

Client-side ship placement lives in `web/static/battleship.js`; the placement
grid hands the complete fleet to `/lock` as JSON, which the server validates
(`validate_fleet`) before storing.

The home page (`/`) and `/battleship` are linked via a nav bar in
`templates/base.html`.
