"""Shared session/identity framework for simple one-on-one games.

Every game in the web app shares the same matchmaking flow:

- the creator opens a game and gets a private player token plus a join link
- a second player joins via the one-time join link and gets their own token
- games expire after 24h and are cleaned up by a background task
- anyone with just the game id sees the game as a spectator

This module owns the generic database tables (match_sessions, match_players,
match_join_tokens, match_events) and the session logic. Game-specific rules
(state, moves, turns, win conditions) live in subclasses, which pick a
game_type, the player sides, the initial state and the status transitions.
"""

import datetime
import json
import random
import secrets
import string
import sqlite3

from configuration import GAMES_DB

DEFAULT_EXPIRY_HOURS = 24


def make_game_id(length=8):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def make_token(length=32):
    return secrets.token_urlsafe(length)


class GameManager:
    game_type = "generic"

    # sides the first and the second player get, e.g. ("white", "black")
    sides = ("A", "B")
    expiry_hours = DEFAULT_EXPIRY_HOURS

    def __init__(self, db_path=GAMES_DB):
        self.db_path = db_path
        self.init_db()

    @property
    def first_side(self):
        return self.sides[0]

    @property
    def second_side(self):
        return self.sides[1]

    # a game moves to this status as soon as the second player joins
    @property
    def status_after_join(self):
        return "playing"

    # ==================== DB init ====================

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS match_sessions (
                game_id TEXT PRIMARY KEY,
                game_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting',
                turn_side TEXT,
                state TEXT NOT NULL DEFAULT '{}',
                move_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                winner TEXT DEFAULT NULL,
                result_reason TEXT DEFAULT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS match_players (
                player_token TEXT PRIMARY KEY,
                game_id TEXT NOT NULL,
                side TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT '{}',
                ready INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES match_sessions(game_id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS match_join_tokens (
                join_token TEXT PRIMARY KEY,
                game_id TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES match_sessions(game_id) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS match_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                side TEXT NOT NULL,
                event_type TEXT NOT NULL,
                data TEXT NOT NULL DEFAULT '{}',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES match_sessions(game_id) ON DELETE CASCADE
            )
            """
        )

        conn.commit()
        conn.close()

    # ==================== JSON state helpers ====================

    @staticmethod
    def _loads(text, default=None):
        if default is None:
            default = {}
        try:
            return json.loads(text) if text else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _dumps(obj):
        return json.dumps(obj, ensure_ascii=False)

    def initial_state(self):
        return {}

    # ==================== Lifecycle ====================

    def create_session(self, player_state=None):
        game_id = make_game_id()
        creator_token = make_token()
        join_token = make_token()

        now = datetime.datetime.utcnow()
        expires_at = now + datetime.timedelta(hours=self.expiry_hours)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO match_sessions (game_id, game_type, status, state, expires_at) "
                "VALUES (?, ?, 'waiting', ?, ?)",
                (game_id, self.game_type, self._dumps(self.initial_state()), expires_at.isoformat()),
            )
            cursor.execute(
                "INSERT INTO match_players (player_token, game_id, side, state) VALUES (?, ?, ?, ?)",
                (creator_token, game_id, self.first_side, self._dumps(player_state or {})),
            )
            cursor.execute(
                "INSERT INTO match_join_tokens (join_token, game_id) VALUES (?, ?)",
                (join_token, game_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return self.create_session(player_state)
        conn.close()
        return game_id, creator_token, join_token

    def get_session(self, game_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT game_id, game_type, status, turn_side, state, move_count, created_at, "
            "expires_at, winner, result_reason FROM match_sessions WHERE game_id = ?",
            (game_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None
        return {
            "game_id": row[0],
            "game_type": row[1],
            "status": row[2],
            "turn_side": row[3],
            "state": self._loads(row[4]),
            "move_count": row[5],
            "created_at": row[6],
            "expires_at": row[7],
            "winner": row[8],
            "result_reason": row[9],
        }

    def get_players(self, game_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT player_token, game_id, side, state, ready, created_at "
            "FROM match_players WHERE game_id = ? ORDER BY created_at",
            (game_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "player_token": r[0],
                "game_id": r[1],
                "side": r[2],
                "state": self._loads(r[3]),
                "ready": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]

    def get_player(self, player_token):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT player_token, game_id, side, state, ready, created_at "
            "FROM match_players WHERE player_token = ?",
            (player_token,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None
        return {
            "player_token": row[0],
            "game_id": row[1],
            "side": row[2],
            "state": self._loads(row[3]),
            "ready": row[4],
            "created_at": row[5],
        }

    def validate_join_token(self, join_token):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT game_id, used FROM match_join_tokens WHERE join_token = ?",
            (join_token,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None, "Invalid invite link"
        if row[1]:
            return None, "This invite link has already been used"

        game = self.get_session(row[0])
        if not game:
            return None, "Game not found"
        if game["status"] != "waiting":
            return None, "This game is no longer accepting players"

        return game, None

    def join_session(self, game_id, join_token):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT used FROM match_join_tokens WHERE join_token = ? AND game_id = ?",
            (join_token, game_id),
        )
        result = cursor.fetchone()
        if not result:
            conn.close()
            return None, "Invalid invite link"
        if result[0]:
            conn.close()
            return None, "This invite link has already been used"

        cursor.execute("SELECT status FROM match_sessions WHERE game_id = ?", (game_id,))
        game = cursor.fetchone()
        if not game or game[0] != "waiting":
            conn.close()
            return None, "This game is no longer available to join"

        second_token = make_token()

        cursor.execute(
            "UPDATE match_join_tokens SET used = 1 WHERE join_token = ?", (join_token,)
        )
        cursor.execute(
            "INSERT INTO match_players (player_token, game_id, side) VALUES (?, ?, ?)",
            (second_token, game_id, self.second_side),
        )
        cursor.execute(
            "UPDATE match_sessions SET status = ?, turn_side = ? WHERE game_id = ?",
            (self.status_after_join, self.first_side, game_id),
        )

        conn.commit()
        conn.close()
        return second_token, None

    def get_unused_join_token(self, game_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT join_token FROM match_join_tokens WHERE game_id = ? AND used = 0 LIMIT 1",
            (game_id,),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    # ==================== Transitions & events ====================

    def set_status(self, game_id, status, winner=None, result_reason=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE match_sessions SET status = ?, winner = ?, result_reason = ? WHERE game_id = ?",
            (status, winner, result_reason, game_id),
        )
        conn.commit()
        conn.close()

    def set_turn(self, game_id, side):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE match_sessions SET turn_side = ? WHERE game_id = ?",
            (side, game_id),
        )
        conn.commit()
        conn.close()

    def update_session_state(self, game_id, state):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE match_sessions SET state = ? WHERE game_id = ?",
            (self._dumps(state), game_id),
        )
        conn.commit()
        conn.close()

    def update_player_state(self, player_token, state, ready=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if ready is None:
            cursor.execute(
                "UPDATE match_players SET state = ? WHERE player_token = ?",
                (self._dumps(state), player_token),
            )
        else:
            cursor.execute(
                "UPDATE match_players SET state = ?, ready = ? WHERE player_token = ?",
                (self._dumps(state), int(ready), player_token),
            )
        conn.commit()
        conn.close()

    def add_event(self, game_id, side, event_type, data=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO match_events (game_id, side, event_type, data) VALUES (?, ?, ?, ?)",
            (game_id, side, event_type, self._dumps(data or {})),
        )
        conn.commit()
        conn.close()

    def get_events(self, game_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, game_id, side, event_type, data, timestamp "
            "FROM match_events WHERE game_id = ? ORDER BY id",
            (game_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": r[0],
                "game_id": r[1],
                "side": r[2],
                "event_type": r[3],
                "data": self._loads(r[4]),
                "timestamp": r[5],
            }
            for r in rows
        ]

    def increment_move_count(self, game_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE match_sessions SET move_count = move_count + 1 WHERE game_id = ?",
            (game_id,),
        )
        conn.commit()
        conn.close()

    # ==================== Maintenance ====================

    def list_games(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT game_id, game_type, status, move_count, created_at, expires_at, winner, result_reason "
            "FROM match_sessions ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        conn.close()

        games = []
        for row in rows:
            game = {
                "game_id": row[0],
                "game_type": row[1],
                "status": row[2],
                "move_count": row[3],
                "created_at": row[4],
                "expires_at": row[5],
                "winner": row[6],
                "result_reason": row[7],
            }
            game["players"] = {p["side"]: True for p in self.get_players(row[0])}
            games.append(game)
        return games

    def cleanup_expired(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT game_id FROM match_sessions WHERE expires_at < datetime('now')")
        expired = [row[0] for row in cursor.fetchall()]

        for game_id in expired:
            cursor.execute("DELETE FROM match_events WHERE game_id = ?", (game_id,))
            cursor.execute("DELETE FROM match_players WHERE game_id = ?", (game_id,))
            cursor.execute("DELETE FROM match_join_tokens WHERE game_id = ?", (game_id,))
            cursor.execute("DELETE FROM match_sessions WHERE game_id = ?", (game_id,))

        conn.commit()
        conn.close()
        return len(expired)
