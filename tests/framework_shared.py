"""Shared framework invariants, run against every registered game type.

These are the guarantees the generic matchmaking layer promises for ALL games
(chess, battleship, and anything added later): create -> waiting, join via
one-time token -> status/turn set, invalid/used tokens rejected, spectators
render, admin lists the type, expired games get cleaned up.

Run:  python tests/framework_shared.py
"""

import re
import sys

sys.path.insert(0, "/home/chirkov/Develop/chess_bot")
sys.path.insert(0, "/home/chirkov/Develop/chess_bot/tests")

from common import configure_test_db

configure_test_db()


def run():
    import sqlite3

    from configuration import GAMES_DB
    from fastapi.testclient import TestClient

    import web.main as wm

    client = TestClient(wm.app, follow_redirects=False)

    # (manager, game page prefix, create route) — every game type registered
    game_specs = [
        (wm.gm, "/game/", "/games/create"),
        (wm.bsm, "/battleship/game/", "/battleship/create"),
    ]

    all_types = set()

    for manager, prefix, create_path in game_specs:
        all_types.add(manager.game_type)
        gtype = manager.game_type

        # create -> waiting, one player
        r = client.post(create_path)
        assert r.status_code == 303, (gtype, r.status_code)
        m = re.match(rf"^{prefix}([a-z0-9]{{8}})\?player=([^&]+)$", r.headers["location"])
        assert m, (gtype, r.headers["location"])
        gid, creator_token = m.group(1), m.group(2)

        game = manager.get_session(gid)
        assert game["status"] == "waiting", (gtype, game["status"])
        players = manager.get_players(gid)
        assert len(players) == 1 and players[0]["side"] == manager.first_side, (gtype, players)

        join_tok = manager.get_unused_join_token(gid)
        assert join_tok, gtype

        # creator page shows the share link
        r = client.get(f"{prefix}{gid}?player={creator_token}")
        assert r.status_code == 200 and f"token={join_tok}" in r.text, gtype

        # spectator page renders (no player token) without crashing
        r = client.get(f"{prefix}{gid}")
        assert r.status_code == 200, gtype

        # join via one-time token
        r = client.post(f"{prefix}{gid}/join", data={"join_token": join_tok})
        assert r.status_code == 303, (gtype, r.headers["location"])
        second_token = re.match(rf"^{prefix}[a-z0-9]{{8}}\?player=([^&]+)$", r.headers["location"]).group(1)

        game = manager.get_session(gid)
        assert game["status"] == manager.status_after_join, (gtype, game["status"])
        assert game["turn_side"] == manager.first_side, (gtype, game["turn_side"])
        players = manager.get_players(gid)
        assert len(players) == 2, (gtype, len(players))
        assert {p["side"] for p in players} == set(manager.sides), (gtype, players)

        # join token is now used -> re-join rejected
        r = client.post(f"{prefix}{gid}/join", data={"join_token": join_tok})
        assert r.status_code == 303, gtype
        assert "error" in r.headers["location"], (gtype, r.headers["location"])

        # bogus token rejected
        r = client.get(f"{prefix}{gid}/join?token=not-a-real-token")
        assert r.status_code == 200 and "error" not in r.headers.get("location", ""), gtype

        # second player's page renders
        r = client.get(f"{prefix}{gid}?player={second_token}")
        assert r.status_code == 200, gtype

    # admin lists every registered type
    r = client.get("/admin?token=x")
    assert r.status_code == 404, "admin without token should 404"
    r = client.get("/admin")
    assert r.status_code == 404

    listed = {g["game_type"] for g in wm.gm.list_games()}
    assert all_types.issubset(listed), (all_types, listed)

    # cleanup_expired removes backdated games across all types
    gid_exp, _, _ = wm.gm.create_web_game()
    conn = sqlite3.connect(GAMES_DB)
    conn.execute(
        "UPDATE match_sessions SET expires_at = ? WHERE game_id = ?",
        ("2000-01-01 00:00:00", gid_exp),
    )
    conn.commit()
    conn.close()
    deleted = wm.gm.cleanup_expired()
    assert deleted >= 1, deleted
    assert wm.gm.get_session(gid_exp) is None

    print("framework_shared: OK")


if __name__ == "__main__":
    run()
