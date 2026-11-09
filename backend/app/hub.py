import asyncio
import json
from typing import Any

from fastapi import WebSocket


class Hub:
    """In-memory fan-out to connected browsers. Fine for one API process; several replicas would
    need a shared channel such as Postgres LISTEN/NOTIFY or Redis pub/sub."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def join(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def leave(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, event: dict[str, Any]) -> None:
        message = json.dumps(event, default=str)
        async with self._lock:
            clients = list(self._clients)
        dead = []
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.leave(ws)

    @property
    def size(self) -> int:
        return len(self._clients)


hub = Hub()
