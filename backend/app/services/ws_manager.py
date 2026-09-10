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
        self._message_queues: dict[int, asyncio.Queue] = defaultdict(asyncio.Queue)

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket, subprotocol: str | None = None) -> None:
        await websocket.accept(subprotocol=subprotocol)
        async with self._lock:
            self._connections[user_id].append(websocket)
        logger.info("WebSocket connected for user %d (total: %d)", user_id, len(self._connections[user_id]))

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id, [])
            if websocket in sockets:
                sockets.remove(websocket)
            if not sockets:
                self._connections.pop(user_id, None)
        logger.info("WebSocket disconnected for user %d (remaining: %d)", user_id, len(self._connections.get(user_id, [])))

    async def send_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        message = json.dumps(payload)
        async with self._lock:
            sockets = list(self._connections.get(user_id, []))
        stale: list[WebSocket] = []
        for ws in sockets:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
                else:
                    stale.append(ws)
            except Exception as e:
                logger.warning("Failed to send message to user %d: %s", user_id, e)
                stale.append(ws)
        for ws in stale:
            await self.disconnect(user_id, ws)

    def notify_from_thread(self, user_id: int, payload: dict[str, Any]) -> None:
        if self._loop is None:
            logger.warning("Cannot notify user %d: event loop not bound", user_id)
            return
        future = asyncio.run_coroutine_threadsafe(self.send_to_user(user_id, payload), self._loop)
        try:
            future.result(timeout=15)
        except Exception as e:
            logger.error("Failed to notify user %d from thread: %s", user_id, e)

    async def broadcast(self, payload: dict[str, Any], exclude_user: int | None = None) -> None:
        message = json.dumps(payload)
        async with self._lock:
            all_sockets = [(uid, ws) for uid, sockets in self._connections.items() for ws in sockets if uid != exclude_user]

        for user_id, ws in all_sockets:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
            except Exception as e:
                logger.warning("Failed to broadcast to user %d: %s", user_id, e)

    def get_connection_count(self, user_id: int) -> int:
        return len(self._connections.get(user_id, []))

    def get_total_connections(self) -> int:
        return sum(len(sockets) for sockets in self._connections.values())


manager = ConnectionManager()
