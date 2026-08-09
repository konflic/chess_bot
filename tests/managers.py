"""Manager-level flow checks (no web layer): battleship + chess on a temp DB.

Run:  python tests/managers.py
"""

import sys

sys.path.insert(0, "/home/chirkov/Develop/chess_bot")
sys.path.insert(0, "/home/chirkov/Develop/chess_bot/tests")

from common import VALID_FLEET, fresh_db
from core.battleship_manager import BattleshipManager
from core.game_manager import ChessGameManager


def run():
    db = fresh_db()

    # ---- battleship manager flow ----
    bsm = BattleshipManager(db_path=db)
    gid, t1, join = bsm.create_battleship_game()
    assert gid and t1 and join
    game = bsm.get_battleship_game(gid)
    assert game["status"] == "waiting" and len(game["players"]) == 1
    assert bsm.validate_join_token(join)[1] is None
    t2, err = bsm.join_session(gid, join)
    assert t2 and not err
    game = bsm.get_battleship_game(gid)
    assert game["status"] == "placing" and game["turn_side"] == "A"

    r = bsm.submit_fleet(gid, t1, VALID_FLEET)
    assert r["success"], r
    assert bsm.get_battleship_game(gid)["status"] == "placing", "game should stay placing"
    r = bsm.submit_fleet(gid, t2, VALID_FLEET[:9])
    assert not r["success"], "invalid fleet accepted"
    r = bsm.submit_fleet(gid, t2, VALID_FLEET)
    assert r["success"], r
    game = bsm.get_battleship_game(gid)
    assert game["status"] == "playing" and game["turn_side"] == "A"

    r = bsm.make_shot(gid, t1, "A1")
    assert r["success"] and r["result"] == "hit", r
    assert bsm.get_battleship_game(gid)["turn_side"] == "A", "hit should keep turn"
    r = bsm.make_shot(gid, t2, "A1")
    assert not r["success"] and r["error"] == "Not your turn", r
    r = bsm.make_shot(gid, t1, "A9")
    assert r["success"] and r["result"] == "miss", r
    assert bsm.get_battleship_game(gid)["turn_side"] == "B", "miss should switch turn"

    for cell in ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "C1", "C2", "C3",
                 "D1", "D2", "E1", "E2", "F1", "F2", "G1", "G3", "G5", "G7"]:
        r = bsm.make_shot(gid, t2, cell)
        assert r["success"], (cell, r)
    game = bsm.get_battleship_game(gid)
    assert game["status"] == "finished" and game["winner"] == "B" and game["result_reason"] == "all_sunk", game

    # resign flow
    gid2, t1b, jt2 = bsm.create_battleship_game()
    t2b, _ = bsm.join_session(gid2, jt2)
    bsm.submit_fleet(gid2, t1b, VALID_FLEET)
    bsm.submit_fleet(gid2, t2b, VALID_FLEET)
    r = bsm.resign(gid2, t1b)
    assert r["success"] and r["winner"] == "B", r
    game = bsm.get_battleship_game(gid2)
    assert game["status"] == "finished" and game["result_reason"] == "resign"

    # ---- chess manager flow ----
    gm = ChessGameManager(db_path=db)
    gid3, wt, jt3 = gm.create_web_game()
    assert gm.get_web_game(gid3)["fen"].startswith("rnbqkbnr")
    assert gm.get_web_game(gid3)["status"] == "waiting"
    bt, err = gm.join_web_game(gid3, jt3)
    assert bt and not err
    assert gm.get_web_game(gid3)["status"] == "playing"
    r = gm.make_web_move(gid3, wt, "e4")
    assert r["success"], r
    r = gm.make_web_move(gid3, bt, "e5")
    assert r["success"], r
    assert gm.get_web_moves(gid3)[0]["color"] == "white"
    fen = gm.get_web_game(gid3)["fen"]
    assert "4P3" in fen and "4p3" in fen, fen
    r = gm.make_web_move(gid3, wt, "Nf3")
    assert r["success"], r
    r = gm.make_web_move(gid3, bt, "Nc6")
    assert r["success"], r
    r = gm.resign_web_game(gid3, wt)
    assert r["success"] and r["winner"] == "black", r

    print("managers: OK")


if __name__ == "__main__":
    run()
