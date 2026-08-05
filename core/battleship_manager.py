"""Battleship manager: ties the shared session framework to the battleship rules.

Lifecycle: waiting -> placing (both joined) -> playing (both locked) -> finished.
"""

from core.game_framework import GameManager
from core import battleship


class BattleshipManager(GameManager):
    game_type = "battleship"
    sides = ("A", "B")

    @property
    def status_after_join(self):
        return "placing"

    @staticmethod
    def opponent(side):
        return "B" if side == "A" else "A"

    # ==================== Lifecycle ====================

    def create_battleship_game(self):
        return self.create_session()

    def get_battleship_game(self, game_id):
        game = self.get_session(game_id)
        if not game:
            return None
        game["players"] = self.get_players(game_id)
        return game

    # ==================== Placement ====================

    def submit_fleet(self, game_id, player_token, ships):
        game = self.get_battleship_game(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}
        if game["status"] not in ("waiting", "placing"):
            return {"success": False, "error": "Placement is not available right now"}

        player = self.get_player(player_token)
        if not player or player["game_id"] != game_id:
            return {"success": False, "error": "Player not found in this game"}

        ok, error = battleship.validate_fleet(ships)
        if not ok:
            return {"success": False, "error": error}

        state = player["state"]
        state["fleet"] = ships
        self.update_player_state(player_token, state, ready=True)

        players = self.get_players(game_id)
        if len(players) == 2 and all(p["ready"] for p in players):
            self.set_status(game_id, "playing", winner=None, result_reason=None)
            self.set_turn(game_id, self.first_side)

        return {"success": True}

    # ==================== Shooting ====================

    def make_shot(self, game_id, player_token, cell):
        game = self.get_battleship_game(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}
        if game["status"] != "playing":
            return {"success": False, "error": "Game is not in progress"}

        player = self.get_player(player_token)
        if not player or player["game_id"] != game_id:
            return {"success": False, "error": "Player not found in this game"}
        if game["turn_side"] != player["side"]:
            return {"success": False, "error": "Not your turn"}

        my_side = player["side"]
        opp_side = self.opponent(my_side)
        opponent = next((p for p in game["players"] if p["side"] == opp_side), None)
        if not opponent:
            return {"success": False, "error": "Opponent not found"}

        opp_state = opponent["state"]
        shots_received = opp_state.setdefault("shots_received", {})
        outcome = battleship.apply_shot(opp_state.get("fleet", []), shots_received, cell)
        if outcome.get("error"):
            return {"success": False, "error": outcome["error"]}

        my_state = player["state"]
        my_state.setdefault("shots_made", {})[cell.strip().upper()] = outcome["result"]

        self.update_player_state(opponent["player_token"], opp_state)
        self.update_player_state(player_token, my_state)
        self.increment_move_count(game_id)
        self.add_event(
            game_id,
            my_side,
            "shot",
            {
                "cell": cell.strip().upper(),
                "result": outcome["result"],
                "sunk": outcome["sunk"],
            },
        )

        if outcome["ships_left"] == 0:
            self.set_status(game_id, "finished", winner=my_side, result_reason="all_sunk")
        elif outcome["result"] == "miss":
            self.set_turn(game_id, opp_side)

        return {
            "success": True,
            "result": outcome["result"],
            "sunk": outcome["sunk"],
            "ships_left": outcome["ships_left"],
        }

    def resign(self, game_id, player_token):
        game = self.get_battleship_game(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}
        if game["status"] != "playing":
            return {"success": False, "error": "Game is not in progress"}

        player = self.get_player(player_token)
        if not player or player["game_id"] != game_id:
            return {"success": False, "error": "Player not found in this game"}

        winner = self.opponent(player["side"])
        self.set_status(game_id, "finished", winner=winner, result_reason="resign")
        self.add_event(game_id, player["side"], "resign", {"winner": winner})
        return {"success": True, "winner": winner, "result_reason": "resign"}
