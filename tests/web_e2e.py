"""HTTP end-to-end flow via TestClient: chess + battleship + locale.

Uses a temp DB and follow_redirects=False. The lang cookie persists per
client, so assert English before switching to RU.

Run:  python tests/web_e2e.py
"""

import json
import re
import sys

sys.path.insert(0, "/home/chirkov/Develop/chess_bot")
sys.path.insert(0, "/home/chirkov/Develop/chess_bot/tests")

from common import VALID_FLEET, configure_test_db

configure_test_db()

LOC_RE = re.compile(r"^(/game|/battleship/game)/([a-z0-9]{8})\?player=([^&]+)$")


def run():
    from fastapi.testclient import TestClient

    import web.main as wm

    client = TestClient(wm.app, follow_redirects=False)

    r = client.get("/")
    assert r.status_code == 200 and "Battleship" in r.text, r.text[:200]
    r = client.get("/battleship")
    assert r.status_code == 200 and "Battleship" in r.text

    # ---- battleship full flow ----
    r = client.post("/battleship/create")
    assert r.status_code == 303
    m = LOC_RE.match(r.headers["location"])
    assert m, r.headers["location"]
    gid, tok_a = m.group(2), m.group(3)

    join_tok = wm.bsm.get_unused_join_token(gid)
    assert join_tok

    r = client.get(f"/battleship/game/{gid}?player={tok_a}")
    assert r.status_code == 200 and "Waiting for opponent" in r.text
    assert f"token={join_tok}" in r.text

    r = client.get(f"/battleship/game/{gid}/join?token={join_tok}")
    assert r.status_code == 200

    r = client.post(f"/battleship/game/{gid}/join", data={"join_token": join_tok})
    assert r.status_code == 303
    tok_b = LOC_RE.match(r.headers["location"]).group(3)

    r = client.get(f"/battleship/game/{gid}?player={tok_a}")
    assert "Place your ships" in r.text

    r = client.post(f"/battleship/game/{gid}/lock", data={"player_token": tok_a, "fleet": json.dumps(VALID_FLEET)})
    assert r.status_code == 303
    r = client.post(f"/battleship/game/{gid}/lock", data={"player_token": tok_b, "fleet": json.dumps(VALID_FLEET)})
    assert r.status_code == 303

    g = wm.bsm.get_battleship_game(gid)
    assert g["status"] == "playing" and g["turn_side"] == "A", g

    r = client.post(f"/battleship/game/{gid}/shoot", data={"player_token": tok_a, "cell": "A1"})
    assert r.status_code == 303 and "shot_hit" in r.headers["location"]
    assert wm.bsm.get_battleship_game(gid)["turn_side"] == "A"

    r = client.post(f"/battleship/game/{gid}/shoot", data={"player_token": tok_b, "cell": "A1"})
    assert r.status_code == 303 and "error=Not+your+turn" in r.headers["location"]

    r = client.post(f"/battleship/game/{gid}/shoot", data={"player_token": tok_a, "cell": "A9"})
    assert "shot_miss" in r.headers["location"]
    assert wm.bsm.get_battleship_game(gid)["turn_side"] == "B"

    r = client.post(f"/battleship/game/{gid}/shoot", data={"player_token": tok_b, "cell": "A1"})
    assert r.status_code == 303 and "shot_hit" in r.headers["location"]
    r = client.post(f"/battleship/game/{gid}/shoot", data={"player_token": tok_b, "cell": "A1"})
    assert r.status_code == 303 and "already+shot" in r.headers["location"]

    for cell in ["A2", "A3", "A4", "B1", "B2", "B3", "C1", "C2", "C3",
                 "D1", "D2", "E1", "E2", "F1", "F2", "G1", "G3", "G5", "G7"]:
        r = client.post(f"/battleship/game/{gid}/shoot", data={"player_token": tok_b, "cell": cell})
        assert r.status_code == 303, cell
    g = wm.bsm.get_battleship_game(gid)
    assert g["status"] == "finished" and g["winner"] == "B" and g["result_reason"] == "all_sunk", g
    r = client.get(f"/battleship/game/{gid}?player={tok_b}")
    assert "You win!" in r.text and "Shots" in r.text and "×" in r.text

    # ---- battleship resign ----
    r = client.post("/battleship/create")
    m = LOC_RE.match(r.headers["location"])
    gid2, tok_a2 = m.group(2), m.group(3)
    jt2 = wm.bsm.get_unused_join_token(gid2)
    client.post(f"/battleship/game/{gid2}/join", data={"join_token": jt2})
    client.post(f"/battleship/game/{gid2}/lock", data={"player_token": tok_a2, "fleet": json.dumps(VALID_FLEET)})
    r = client.post(f"/battleship/game/{gid2}/resign", data={"player_token": tok_a2})
    assert r.status_code == 303 and "error" in r.headers["location"], "resign during placing must fail"
    g = wm.bsm.get_battleship_game(gid2)
    assert g["status"] == "placing", g

    # join + lock both fleets, then resign
    r = client.post("/battleship/create")
    m = LOC_RE.match(r.headers["location"])
    gid3, tok_a3 = m.group(2), m.group(3)
    jt3 = wm.bsm.get_unused_join_token(gid3)
    r = client.post(f"/battleship/game/{gid3}/join", data={"join_token": jt3})
    tok_b3 = LOC_RE.match(r.headers["location"]).group(3)
    client.post(f"/battleship/game/{gid3}/lock", data={"player_token": tok_a3, "fleet": json.dumps(VALID_FLEET)})
    client.post(f"/battleship/game/{gid3}/lock", data={"player_token": tok_b3, "fleet": json.dumps(VALID_FLEET)})
    r = client.post(f"/battleship/game/{gid3}/resign", data={"player_token": tok_a3})
    assert r.status_code == 303
    g = wm.bsm.get_battleship_game(gid3)
    assert g["status"] == "finished" and g["winner"] == "B" and g["result_reason"] == "resign", g

    # ---- chess flow ----
    r = client.post("/games/create")
    assert r.status_code == 303
    m = LOC_RE.match(r.headers["location"])
    gid3, tok_w = m.group(2), m.group(3)
    jt3 = wm.gm.get_unused_join_token(gid3)
    r = client.get(f"/game/{gid3}?player={tok_w}")
    assert r.status_code == 200 and ("e2e4" in r.text or "svg" in r.text)
    r = client.post(f"/game/{gid3}/join", data={"join_token": jt3})
    m = LOC_RE.match(r.headers["location"])
    tok_b3 = m.group(3)
    r = client.post(f"/game/{gid3}/move", data={"player_token": tok_w, "move": "e4"})
    assert r.status_code == 303
    r = client.post(f"/game/{gid3}/move", data={"player_token": tok_b3, "move": "e5"})
    assert r.status_code == 303
    r = client.get(f"/game/{gid3}?player={tok_w}")
    assert r.status_code == 200 and "e2e4" in r.text

    # ---- spectator ----
    r = client.get(f"/battleship/game/{gid}")
    assert r.status_code == 200 and "Shots" in r.text
    r = client.get(f"/game/{gid3}")
    assert r.status_code == 200 and "Moves" in r.text

    # ---- 404 for unknown game ----
    r = client.get("/game/zzzzzzzz")
    assert r.status_code == 404

    # ---- russian locale ----
    r = client.post("/lang/ru")
    assert r.status_code == 303
    r = client.get("/")
    assert r.status_code == 200 and "Морской бой" in r.text
    r = client.get("/battleship")
    assert r.status_code == 200 and "Играйте в морской бой" in r.text

    print("web_e2e: OK")


if __name__ == "__main__":
    run()
