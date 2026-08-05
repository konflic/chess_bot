import datetime
import sqlite3

import chess

from core.constants import START_FEN
from core.game_framework import GameManager


class ChessGameManager(GameManager):
    game_type = "chess"
    sides = ("white", "black")

    def initial_state(self):
        return {"fen": START_FEN}

    def init_db(self):
        super().init_db()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Legacy tables from the pre-framework web and Telegram versions are
        # dropped. Games live only 24h, so nothing is worth migrating.
        for table in (
            "web_games",
            "web_players",
            "web_moves",
            "web_join_tokens",
            "games",
            "moves",
            "ping_history",
            "active_games",
        ):
            cursor.execute(f"DROP TABLE IF EXISTS {table}")

        conn.commit()
        conn.close()

    # ==================== Web methods ====================

    def create_web_game(self):
        return self.create_session()

    def get_web_game(self, game_id):
        game = self.get_session(game_id)
        if not game:
            return None
        return {
            "game_id": game["game_id"],
            "fen": game["state"].get("fen", START_FEN),
            "status": game["status"],
            "move_count": game["move_count"],
            "created_at": game["created_at"],
            "expires_at": game["expires_at"],
            "winner": game["winner"],
            "result_reason": game["result_reason"],
        }

    def get_web_player(self, player_token):
        player = self.get_player(player_token)
        if not player:
            return None
        return {
            "player_token": player["player_token"],
            "game_id": player["game_id"],
            "color": player["side"],
        }

    def join_web_game(self, game_id, join_token):
        return self.join_session(game_id, join_token)

    def get_web_moves(self, game_id, created_at=None):
        if created_at:
            start = datetime.datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        else:
            start = None

        events = [e for e in self.get_events(game_id) if e["event_type"] == "move"]
        moves = []
        for i, event in enumerate(events, 1):
            san = event["data"].get("san", "")
            uci = event["data"].get("uci", "")
            t = ""
            if start:
                dt = datetime.datetime.strptime(event["timestamp"], "%Y-%m-%d %H:%M:%S")
                secs = int((dt - start).total_seconds())
                h = secs // 3600
                m = (secs % 3600) // 60
                s = secs % 60
                t = f"{h}:{m:02d}:{s:02d}"
            display = uci[:2] + "->" + uci[2:4] if len(uci) >= 4 else san
            if len(uci) > 4:
                display += uci[4:]
            moves.append({"number": i, "time": t, "color": event["side"], "display": display})

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
                "UPDATE match_sessions SET state = ?, status = ?, winner = ?, result_reason = ?, "
                "move_count = move_count + 1 WHERE game_id = ?",
                (self._dumps({"fen": board.fen()}), game_status, winner, result_reason, game_id),
            )
            conn.commit()
            conn.close()

            self.add_event(game_id, player["color"], "move", {"san": move_san, "uci": move_uci})

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
        self.set_status(game_id, "finished", winner=winner, result_reason="resign")

        return {"success": True, "winner": winner, "result_reason": "resign"}
