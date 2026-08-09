"""Realtime (SSE) checks: live update delivery, no-leak payloads, failures.

Two layers:
- unit: ConnectionManager connect/notify/close_game/disconnect semantics
- integration: a real uvicorn subprocess on a free port (SSE only works over
  a real stream — httpx's ASGITransport buffers the whole response), where we
  open an event stream, mutate the game via HTTP, and assert events arrive.

Run:  python tests/realtime_sse.py
"""

import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, "/home/chirkov/Develop/chess_bot")
sys.path.insert(0, "/home/chirkov/Develop/chess_bot/tests")

from common import VALID_FLEET


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _unit_checks():
    import asyncio

    from web.realtime import ConnectionManager, sse_format

    async def scenario():
        rtm = ConnectionManager()
        gid = "gameunit1"

        q = rtm.connect(gid)
        assert rtm.subscribers(gid) == 1
        await rtm.notify(gid, {"type": "update", "game_id": gid, "reason": "join"})
        assert q.get_nowait() == {"type": "update", "game_id": gid, "reason": "join"}
        assert q.empty()

        await rtm.close_game(gid)
        assert q.get_nowait()["reason"] == "expired"
        assert rtm.subscribers(gid) == 0

        await rtm.notify(gid, {"type": "update", "game_id": gid, "reason": "move"})  # no crash

        q2 = rtm.connect(gid)
        rtm.disconnect(gid, q2)
        assert rtm.subscribers(gid) == 0
        await rtm.notify(gid, {"type": "update", "game_id": gid, "reason": "x"})  # no crash

        formatted = sse_format({"type": "update", "reason": "move"})
        assert formatted.startswith("data: ") and formatted.endswith("\n\n")

    asyncio.run(scenario())


def _chunks(resp):
    return resp.aiter_raw().__aiter__()


async def _read_event(chunks, timeout=5.0):
    """Read SSE chunks until a data: line arrives; return the parsed event."""
    buf = b""
    while True:
        try:
            chunk = await asyncio.wait_for(anext(chunks), timeout=timeout)
        except StopAsyncIteration:
            return None
        if not chunk:
            return None
        buf += chunk
        data_lines = [ln for ln in buf.decode().splitlines() if ln.startswith("data: ")]
        if data_lines:
            return json.loads(data_lines[-1][len("data: "):])


async def _assert_silent(ac, gid, timeout=1.5):
    """Open a throwaway stream and assert no event arrives in `timeout` seconds."""
    async with ac.stream("GET", f"/events/game/{gid}") as s:
        chunks = _chunks(s)
        try:
            event = await _read_event(chunks, timeout=timeout)
        except asyncio.TimeoutError:
            return
        raise AssertionError(f"expected no event, got {event}")


def _join_token_from_page(html):
    m = re.search(r"token=([A-Za-z0-9_\-]+)", html)
    assert m, "join token not found on page"
    return m.group(1)


async def _chess_scenario(base):
    import httpx

    async with httpx.AsyncClient(base_url=base, follow_redirects=False) as ac:
        r = await ac.post("/games/create")
        loc = r.headers["location"]
        gid = loc.split("/game/")[1].split("?")[0]
        tok_w = loc.split("player=")[1]

        r = await ac.get(f"/game/{gid}?player={tok_w}")
        assert r.status_code == 200
        join_tok = _join_token_from_page(r.text)

        async with ac.stream("GET", f"/events/game/{gid}") as s:
            chunks = _chunks(s)

            r = await ac.post(f"/game/{gid}/join", data={"join_token": join_tok})
            assert r.status_code == 303
            tok_b = r.headers["location"].split("player=")[1]
            ev = await _read_event(chunks)
            assert ev and ev["reason"] == "join", ev

            # illegal move -> no broadcast
            r = await ac.post(f"/game/{gid}/move", data={"player_token": tok_w, "move": "e7"})
            assert r.status_code == 303 and "error" in r.headers["location"]
            await _assert_silent(ac, gid)

            # valid move -> broadcast
            r = await ac.post(f"/game/{gid}/move", data={"player_token": tok_w, "move": "e4"})
            assert r.status_code == 303
            ev = await _read_event(chunks)
            assert ev and ev["reason"] == "move" and ev["type"] == "update", ev
            assert ev["game_id"] == gid
            assert not any(k in ev for k in ("fen", "fleet", "shots")), ev

            # spectator stream also receives
            async with ac.stream("GET", f"/events/game/{gid}") as spec:
                spec_chunks = _chunks(spec)
                r = await ac.post(f"/game/{gid}/move", data={"player_token": tok_b, "move": "e5"})
                assert r.status_code == 303
                ev = await _read_event(spec_chunks)
                assert ev and ev["reason"] == "move", ev
                ev = await _read_event(chunks)
                assert ev and ev["reason"] == "move", ev

            # resign broadcast
            r = await ac.post(f"/game/{gid}/resign", data={"player_token": tok_b})
            assert r.status_code == 303
            ev = await _read_event(chunks)
            assert ev and ev["reason"] == "resign", ev


async def _battleship_scenario(base):
    import httpx

    async with httpx.AsyncClient(base_url=base, follow_redirects=False) as ac:
        r = await ac.post("/battleship/create")
        loc = r.headers["location"]
        gid = loc.split("/game/")[1].split("?")[0]
        tok_a = loc.split("player=")[1]

        r = await ac.get(f"/battleship/game/{gid}?player={tok_a}")
        assert r.status_code == 200
        join_tok = _join_token_from_page(r.text)

        r = await ac.post(f"/battleship/game/{gid}/join", data={"join_token": join_tok})
        tok_b = r.headers["location"].split("player=")[1]

        async with ac.stream("GET", f"/events/game/{gid}") as s:
            chunks = _chunks(s)
            r = await ac.post(
                f"/battleship/game/{gid}/lock",
                data={"player_token": tok_a, "fleet": json.dumps(VALID_FLEET)},
            )
            assert r.status_code == 303
            ev = await _read_event(chunks)
            assert ev and ev["reason"] == "lock", ev

            # out-of-turn shot -> no broadcast
            r = await ac.post(
                f"/battleship/game/{gid}/shoot",
                data={"player_token": tok_b, "cell": "A1"},
            )
            assert r.status_code == 303 and "error" in r.headers["location"]
            await _assert_silent(ac, gid)

            r = await ac.post(
                f"/battleship/game/{gid}/lock",
                data={"player_token": tok_b, "fleet": json.dumps(VALID_FLEET)},
            )
            assert r.status_code == 303
            ev = await _read_event(chunks)
            assert ev and ev["reason"] == "lock", ev

            r = await ac.post(
                f"/battleship/game/{gid}/shoot",
                data={"player_token": tok_a, "cell": "A1"},
            )
            assert r.status_code == 303
            ev = await _read_event(chunks)
            assert ev and ev["reason"] == "shoot", ev
            assert not any(k in ev for k in ("fen", "fleet", "shots")), ev


async def _integration():
    import httpx

    port = _free_port()
    db = os.path.join(tempfile.mkdtemp(), "sse.db")
    env = {**os.environ, "GAMES_DB": db}
    repo = "/home/chirkov/Develop/chess_bot"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=repo,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        async with httpx.AsyncClient(base_url=base, follow_redirects=False) as ac:
            deadline = time.time() + 15
            while time.time() < deadline:
                try:
                    r = await ac.get("/")
                    if r.status_code == 200:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.2)
            else:
                raise AssertionError("server did not become ready")

        await _chess_scenario(base)
        await _battleship_scenario(base)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def run():
    _unit_checks()
    asyncio.run(_integration())
    print("realtime_sse: OK")


if __name__ == "__main__":
    run()
