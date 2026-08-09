"""Server-Sent Events fan-out for live game updates.

A small in-memory registry mapping game_id -> set of asyncio.Queue. Each SSE
connection owns one queue; the web layer calls notify() after any game state
change and every subscriber of that game receives the event. The payload is
deliberately state-free ({type, game_id, reason}) so the channel is safe for
spectators and never leaks hidden game data (e.g. battleship fleets).

Single-process only: the app runs one uvicorn process, so an in-memory map is
enough. If the app is ever scaled to multiple workers, this transport must be
replaced (Redis pub/sub or per-worker game affinity).
"""

import asyncio
import json


class ConnectionManager:
    def __init__(self):
        self._streams = {}

    def connect(self, game_id):
        queue = asyncio.Queue()
        self._streams.setdefault(game_id, set()).add(queue)
        return queue

    def disconnect(self, game_id, queue):
        subscribers = self._streams.get(game_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._streams.pop(game_id, None)

    async def notify(self, game_id, event):
        for queue in list(self._streams.get(game_id, ())):
            queue.put_nowait(event)

    async def close_game(self, game_id):
        await self.notify(game_id, {"type": "update", "game_id": game_id, "reason": "expired"})
        self._streams.pop(game_id, None)

    def subscribers(self, game_id):
        return len(self._streams.get(game_id, ()))


def sse_format(event) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
