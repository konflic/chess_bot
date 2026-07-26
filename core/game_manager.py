import sqlite3
import random
import string
import chess
import datetime
import secrets

from configuration import GAMES_DB
from core.constants import COMPUTER_PLAYER, START_FEN


def make_game_id():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def make_token(length=32):
    return secrets.token_urlsafe(length)


class ChessGameManager:
    def __init__(self, db_path=GAMES_DB):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # ---- bot tables ----
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT UNIQUE NOT NULL,
                player1_id INTEGER,
                player2_id INTEGER,
                fen TEXT DEFAULT 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                current_turn INTEGER,
                status TEXT DEFAULT 'waiting',
                invite_link TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_move_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        self._apply_games_migrations(cursor)

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT,
                move_san TEXT,
                player_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games (game_id)
            )
        """
        )

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ping_history'"
        )
        table_exists = cursor.fetchone()

        if table_exists:
            cursor.execute("PRAGMA table_info(ping_history)")
            columns = [column[1] for column in cursor.fetchall()]

            if "game_id" not in columns:
                print("Migrating ping_history table to include game_id...")
                cursor.execute("ALTER TABLE ping_history RENAME TO ping_history_old")

                cursor.execute(
                    """
                    CREATE TABLE ping_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        game_id TEXT,
                        player_id INTEGER,
                        last_ping_time TIMESTAMP,
                        UNIQUE(game_id, player_id)
                    )
                """
                )

                cursor.execute(
                    """
                    INSERT INTO ping_history (game_id, player_id, last_ping_time)
                    SELECT 'unknown', player_id, last_ping_time FROM ping_history_old
                """
                )

                cursor.execute("DROP TABLE ping_history_old")
                print("Migration completed successfully!")
        else:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ping_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT,
                    player_id INTEGER,
                    last_ping_time TIMESTAMP,
                    UNIQUE(game_id, player_id)
                )
            """
            )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS active_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER UNIQUE,
                active_game_id TEXT,
                FOREIGN KEY (active_game_id) REFERENCES games (game_id)
            )
        """
        )

        # ---- web tables ----
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS web_games (
                game_id TEXT PRIMARY KEY,
                fen TEXT NOT NULL DEFAULT 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                status TEXT NOT NULL DEFAULT 'waiting',
                move_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                winner TEXT DEFAULT NULL,
                result_reason TEXT DEFAULT NULL
            )
        """
        )

        self._apply_web_games_migrations(cursor)

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS web_players (
                player_token TEXT PRIMARY KEY,
                game_id TEXT NOT NULL,
                color TEXT NOT NULL CHECK(color IN ('white', 'black')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES web_games(game_id) ON DELETE CASCADE
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS web_moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                move_san TEXT NOT NULL,
                move_uci TEXT NOT NULL,
                player_token TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES web_games(game_id) ON DELETE CASCADE
            )
        """
        )

        self._apply_web_moves_migrations(cursor)

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS web_join_tokens (
                join_token TEXT PRIMARY KEY,
                game_id TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES web_games(game_id) ON DELETE CASCADE
            )
        """
        )

        conn.commit()
        conn.close()

    def _apply_games_migrations(self, cursor):
        cursor.execute("PRAGMA table_info(games)")
        columns = [column[1] for column in cursor.fetchall()]

        if "last_move_timestamp" not in columns:
            print("Applying migration: Adding last_move_timestamp column to games table...")
            try:
                cursor.execute("ALTER TABLE games ADD COLUMN last_move_timestamp TIMESTAMP")
                cursor.execute(
                    "UPDATE games SET last_move_timestamp = created_at WHERE last_move_timestamp IS NULL"
                )
                print("Migration completed successfully!")
            except sqlite3.OperationalError as e:
                print(f"Migration failed: {e}")

    # ==================== Bot methods ====================

    def generate_invite_link(self):
        return "".join(random.choices(string.ascii_letters + string.digits, k=12))

    def create_game(self, player1_id, computer_opponent=False, custom_fen=None):
        game_id = "".join(random.choices(string.ascii_letters + string.digits, k=10))
        invite_link = self.generate_invite_link()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        fen = custom_fen if custom_fen else START_FEN

        try:
            if computer_opponent:
                cursor.execute(
                    """
                    INSERT INTO games (game_id, player1_id, player2_id, current_turn, invite_link, status, fen)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (game_id, player1_id, COMPUTER_PLAYER, player1_id, invite_link, "playing", fen),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO games (game_id, player1_id, current_turn, invite_link, fen)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (game_id, player1_id, player1_id, invite_link, fen),
                )

            conn.commit()
            conn.close()
            return game_id, invite_link
        except sqlite3.IntegrityError:
            return self.create_game(player1_id, computer_opponent, custom_fen)

    def join_game(self, invite_link, joining_player_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT game_id, player1_id, player2_id FROM games
            WHERE invite_link = ? AND player2_id IS NULL AND status = 'waiting'
        """,
            (invite_link,),
        )

        result = cursor.fetchone()
        if result:
            game_id, player1_id, _ = result

            cursor.execute(
                """
                SELECT game_id FROM games
                WHERE ((player1_id = ? AND player2_id = ?) OR (player1_id = ? AND player2_id = ?))
                AND status = 'playing'
            """,
                (player1_id, joining_player_id, joining_player_id, player1_id),
            )

            existing_game = cursor.fetchone()
            if existing_game:
                conn.close()
                return None, "existing_game"

            cursor.execute(
                """
                UPDATE games SET player2_id = ?, status = 'playing' WHERE game_id = ?
            """,
                (joining_player_id, game_id),
            )

            conn.commit()
            conn.close()
            return game_id, player1_id

        cursor.execute(
            """
            SELECT game_id, player1_id, player2_id FROM games
            WHERE invite_link = ? AND player1_id IS NULL AND status = 'waiting'
        """,
            (invite_link,),
        )

        result = cursor.fetchone()
        if result:
            game_id, _, player2_id = result

            cursor.execute(
                """
                SELECT game_id FROM games
                WHERE ((player1_id = ? AND player2_id = ?) OR (player1_id = ? AND player2_id = ?))
                AND status = 'playing'
            """,
                (joining_player_id, player2_id, player2_id, joining_player_id),
            )

            existing_game = cursor.fetchone()
            if existing_game:
                conn.close()
                return None, "existing_game"

            cursor.execute("SELECT fen FROM games WHERE game_id = ?", (game_id,))
            fen_result = cursor.fetchone()
            if fen_result:
                board = chess.Board(fen_result[0])
                current_turn = joining_player_id if board.turn else player2_id
            else:
                current_turn = joining_player_id

            cursor.execute(
                """
                UPDATE games SET player1_id = ?, current_turn = ?, status = 'playing' WHERE game_id = ?
            """,
                (joining_player_id, current_turn, game_id),
            )

            conn.commit()
            conn.close()
            return game_id, player2_id

        conn.close()
        return None, None

    def get_game(self, game_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT game_id, player1_id, player2_id, fen, current_turn, status, last_move_timestamp
            FROM games WHERE game_id = ?
        """,
            (game_id,),
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                "game_id": result[0],
                "player1_id": result[1],
                "player2_id": result[2],
                "fen": result[3],
                "current_turn": result[4],
                "status": result[5],
                "last_move_timestamp": result[6],
            }
        return None

    def make_move(self, game_id, move_san, player_id):
        game = self.get_game(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        if game["current_turn"] != player_id:
            return {"success": False, "error": "Not your turn"}

        board = chess.Board(game["fen"])

        try:
            normalized = move_san.lower()
            if normalized and normalized[0] in "nbrqk":
                normalized = normalized[0].upper() + normalized[1:]
            move = board.parse_san(normalized)
            if board.is_legal(move):
                board.push(move)

                if board.is_checkmate():
                    game_status = "finished"
                    winner = player_id
                elif board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
                    game_status = "finished"
                    winner = "draw"
                else:
                    next_player = game["player2_id"] if player_id == game["player1_id"] else game["player1_id"]
                    game_status = "playing"
                    winner = None

                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    UPDATE games
                    SET fen = ?, current_turn = ?, status = ?, last_move_timestamp = CURRENT_TIMESTAMP
                    WHERE game_id = ?
                """,
                    (
                        board.fen(),
                        (next_player if game_status == "playing" else game["current_turn"]),
                        game_status,
                        game_id,
                    ),
                )

                cursor.execute(
                    "INSERT INTO moves (game_id, move_san, player_id) VALUES (?, ?, ?)",
                    (game_id, move_san, player_id),
                )

                conn.commit()
                conn.close()

                return {
                    "success": True,
                    "new_fen": board.fen(),
                    "next_turn": next_player if game_status == "playing" else None,
                    "checkmate": board.is_checkmate(),
                    "stalemate": board.is_stalemate(),
                    "insufficient_material": board.is_insufficient_material(),
                    "winner": winner,
                    "status": game_status,
                }
            else:
                return {"success": False, "error": "Illegal move"}
        except ValueError:
            return {"success": False, "error": "Invalid move notation"}

    def delete_game(self, game_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM games WHERE game_id = ?", (game_id,))
        cursor.execute("DELETE FROM moves WHERE game_id = ?", (game_id,))

        conn.commit()
        conn.close()

    def get_abandoned_games(self, days_threshold=7):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT game_id, player1_id, player2_id, fen, current_turn, status, last_move_timestamp
            FROM games
            WHERE status = 'playing' AND julianday('now') - julianday(last_move_timestamp) > ?
            ORDER BY last_move_timestamp ASC
        """,
            (days_threshold,),
        )

        results = cursor.fetchall()
        conn.close()

        abandoned = []
        for result in results:
            abandoned.append(
                {
                    "game_id": result[0],
                    "player1_id": result[1],
                    "player2_id": result[2],
                    "fen": result[3],
                    "current_turn": result[4],
                    "status": result[5],
                    "last_move_timestamp": result[6],
                }
            )

        return abandoned

    def cleanup_abandoned_games(self, days_threshold=7):
        abandoned = self.get_abandoned_games(days_threshold)
        for game in abandoned:
            self.delete_game(game["game_id"])
        return len(abandoned)

    def _apply_web_games_migrations(self, cursor):
        cursor.execute("PRAGMA table_info(web_games)")
        columns = [column[1] for column in cursor.fetchall()]
        if "winner" not in columns:
            cursor.execute("ALTER TABLE web_games ADD COLUMN winner TEXT DEFAULT NULL")
        if "result_reason" not in columns:
            cursor.execute("ALTER TABLE web_games ADD COLUMN result_reason TEXT DEFAULT NULL")

    def _apply_web_moves_migrations(self, cursor):
        cursor.execute("PRAGMA table_info(web_moves)")
        columns = [column[1] for column in cursor.fetchall()]
        if "move_uci" not in columns:
            cursor.execute("ALTER TABLE web_moves ADD COLUMN move_uci TEXT DEFAULT ''")

    # ==================== Web methods ====================

    def create_web_game(self):
        game_id = make_game_id()
        white_token = make_token()
        join_token = make_token()

        now = datetime.datetime.utcnow()
        expires_at = now + datetime.timedelta(hours=24)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO web_games (game_id, fen, status, expires_at) VALUES (?, ?, 'waiting', ?)",
            (game_id, START_FEN, expires_at.isoformat()),
        )
        cursor.execute(
            "INSERT INTO web_players (player_token, game_id, color) VALUES (?, ?, 'white')",
            (white_token, game_id),
        )
        cursor.execute(
            "INSERT INTO web_join_tokens (join_token, game_id) VALUES (?, ?)",
            (join_token, game_id),
        )

        conn.commit()
        conn.close()

        return game_id, white_token, join_token

    def get_web_game(self, game_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT game_id, fen, status, move_count, created_at, expires_at, winner, result_reason FROM web_games WHERE game_id = ?",
            (game_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "game_id": row[0],
                "fen": row[1],
                "status": row[2],
                "move_count": row[3],
                "created_at": row[4],
                "expires_at": row[5],
                "winner": row[6],
                "result_reason": row[7],
            }
        return None

    def get_web_player(self, player_token):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT player_token, game_id, color FROM web_players WHERE player_token = ?",
            (player_token,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "player_token": row[0],
                "game_id": row[1],
                "color": row[2],
            }
        return None

    def validate_join_token(self, join_token):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT game_id, used FROM web_join_tokens WHERE join_token = ?",
            (join_token,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None, "Invalid invite link"
        if row[1]:
            return None, "This invite link has already been used"

        game = self.get_web_game(row[0])
        if not game:
            return None, "Game not found"
        if game["status"] != "waiting":
            return None, "This game is no longer accepting players"

        return game, None

    def join_web_game(self, game_id, join_token):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT used FROM web_join_tokens WHERE join_token = ? AND game_id = ?",
                       (join_token, game_id))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return None, "Invalid invite link"

        if result[0]:
            conn.close()
            return None, "This invite link has already been used"

        cursor.execute("SELECT status FROM web_games WHERE game_id = ?", (game_id,))
        game = cursor.fetchone()
        if not game or game[0] != "waiting":
            conn.close()
            return None, "This game is no longer available to join"

        black_token = make_token()

        cursor.execute("UPDATE web_join_tokens SET used = 1 WHERE join_token = ?", (join_token,))
        cursor.execute(
            "INSERT INTO web_players (player_token, game_id, color) VALUES (?, ?, 'black')",
            (black_token, game_id),
        )
        cursor.execute("UPDATE web_games SET status = 'playing' WHERE game_id = ?", (game_id,))

        conn.commit()
        conn.close()

        return black_token, None

    def get_web_moves(self, game_id, created_at=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT wm.move_san, wm.move_uci, wm.timestamp, wp.color "
            "FROM web_moves wm "
            "JOIN web_players wp ON wm.player_token = wp.player_token "
            "WHERE wm.game_id = ? ORDER BY wm.id",
            (game_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        if created_at:
            start = datetime.datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        else:
            start = None

        moves = []
        for i, (san, uci, ts, color) in enumerate(rows, 1):
            t = ""
            if start:
                dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                secs = int((dt - start).total_seconds())
                h = secs // 3600
                m = (secs % 3600) // 60
                s = secs % 60
                t = f"{h}:{m:02d}:{s:02d}"
            display = uci[:2] + "->" + uci[2:4] if len(uci) >= 4 else san
            if len(uci) > 4:
                display += uci[4:]
            moves.append({"number": i, "time": t, "color": color, "display": display})

        return moves

    def make_web_move(self, game_id, player_token, move_san):
        game = self.get_web_game(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        if game["status"] != "playing":
            return {"success": False, "error": "Game is not in progress"}

        player = self.get_web_player(player_token)
        if not player or player["game_id"] != game_id:
            return {"success": False, "error": "Player not found in this game"}

        board = chess.Board(game["fen"])
        current_turn_color = "white" if board.turn == chess.WHITE else "black"

        if player["color"] != current_turn_color:
            return {"success": False, "error": "Not your turn"}

        try:
            normalized = move_san.lower()
            if normalized and normalized[0] in "nbrqk":
                normalized = normalized[0].upper() + normalized[1:]
            move = board.parse_san(normalized)
            if not board.is_legal(move):
                return {"success": False, "error": "Illegal move"}

            move_uci = move.uci()
            board.push(move)

            if board.is_checkmate():
                game_status = "finished"
                winner = player["color"]
                result_reason = "checkmate"
            elif board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
                game_status = "finished"
                winner = "draw"
                result_reason = "draw"
            else:
                game_status = "playing"
                winner = None
                result_reason = None

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE web_games SET fen = ?, status = ?, winner = ?, result_reason = ?, move_count = move_count + 1 WHERE game_id = ?",
                (board.fen(), game_status, winner, result_reason, game_id),
            )

            cursor.execute(
                "INSERT INTO web_moves (game_id, move_san, move_uci, player_token) VALUES (?, ?, ?, ?)",
                (game_id, move_san, move_uci, player_token),
            )

            conn.commit()
            conn.close()

            return {
                "success": True,
                "new_fen": board.fen(),
                "status": game_status,
                "winner": winner,
                "result_reason": result_reason,
            }

        except ValueError as e:
            return {"success": False, "error": f"Invalid move notation: {str(e)}"}

    def resign_web_game(self, game_id, player_token):
        game = self.get_web_game(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}
        if game["status"] != "playing":
            return {"success": False, "error": "Game is not in progress"}

        player = self.get_web_player(player_token)
        if not player or player["game_id"] != game_id:
            return {"success": False, "error": "Player not found in this game"}

        winner = "black" if player["color"] == "white" else "white"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE web_games SET status = 'finished', winner = ?, result_reason = 'resign' WHERE game_id = ?",
            (winner, game_id),
        )
        conn.commit()
        conn.close()

        return {"success": True, "winner": winner, "result_reason": "resign"}

    def list_web_games(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT game_id, fen, status, move_count, created_at, expires_at, winner, result_reason "
            "FROM web_games ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()

        games = []
        for row in rows:
            game = {
                "game_id": row[0],
                "status": row[2],
                "move_count": row[3],
                "created_at": row[4],
                "expires_at": row[5],
                "winner": row[6],
                "result_reason": row[7],
            }
            cursor.execute(
                "SELECT color FROM web_players WHERE game_id = ? ORDER BY created_at", (row[0],)
            )
            players = [p[0] for p in cursor.fetchall()]
            game["white"] = True if "white" in players else False
            game["black"] = True if "black" in players else False
            games.append(game)

        conn.close()
        return games

    def cleanup_expired_web_games(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT game_id FROM web_games WHERE expires_at < datetime('now')")
        expired = [row[0] for row in cursor.fetchall()]

        for game_id in expired:
            cursor.execute("DELETE FROM web_moves WHERE game_id = ?", (game_id,))
            cursor.execute("DELETE FROM web_players WHERE game_id = ?", (game_id,))
            cursor.execute("DELETE FROM web_join_tokens WHERE game_id = ?", (game_id,))
            cursor.execute("DELETE FROM web_games WHERE game_id = ?", (game_id,))

        conn.commit()
        conn.close()

        return len(expired)
