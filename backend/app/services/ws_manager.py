from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, list[WebSocket]] = defaultdict(list)
        self._lock: asyncio.Lock | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._lock = asyncio.Lock()

    async def connect(
        self,
        user_id: int,
        websocket: WebSocket,
        subprotocol: str | None = None,
    ) -> None:
        await websocket.accept(subprotocol=subprotocol)
        async with self._get_lock():
            self._connections[user_id].append(websocket)
        logger.info("WebSocket connected: user=%d (user sockets: %d, total users: %d)", user_id, len(self._connections[user_id]), len(self._connections))

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._get_lock():
            sockets = self._connections.get(user_id, [])
            if websocket in sockets:
                sockets.remove(websocket)
            if not sockets:
                self._connections.pop(user_id, None)
        logger.info("WebSocket disconnected: user=%d", user_id)

    async def send_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        message = json.dumps(payload)
        async with self._get_lock():
            sockets = list(self._connections.get(user_id, []))

        stale: list[WebSocket] = []
        for ws in sockets:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
                else:
                    stale.append(ws)
            except Exception as exc:
                logger.warning("Failed sending to user %d socket: %s", user_id, exc)
                stale.append(ws)

        for ws in stale:
            await self.disconnect(user_id, ws)

    async def broadcast(self, payload: dict[str, Any], exclude_user: int | None = None) -> None:
        message = json.dumps(payload)
        async with self._get_lock():
            targets = [
                (uid, ws)
                for uid, sockets in self._connections.items()
                if uid != exclude_user
                for ws in sockets
            ]

        for uid, ws in targets:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
            except Exception as exc:
                logger.warning("Broadcast failure to user %d: %s", uid, exc)

    def notify_from_thread(self, user_id: int, payload: dict[str, Any]) -> None:
        loop = self._loop or (asyncio.get_event_loop() if asyncio.get_event_loop().is_running() else None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.send_to_user(user_id, payload), loop)
        else:
            logger.warning("Cannot notify user %d: no running event loop available", user_id)

    def get_user_socket_count(self, user_id: int) -> int:
        return len(self._connections.get(user_id, []))

    def get_total_connections(self) -> int:
        return sum(len(s) for s in self._connections.values())


manager = ConnectionManager()
