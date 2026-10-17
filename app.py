from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "static" / "index.html"

MAX_MESSAGE_LENGTH = 4_000
MAX_NAME_LENGTH = 30
HISTORY_SIZE = 100

app = FastAPI(
    title="局域网聊天室",
    description="无需安装客户端，在同一局域网内通过浏览器实时聊天。",
)


class ConnectionManager:
    """Track connected browsers and broadcast room events."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._history: deque[dict[str, Any]] = deque(maxlen=HISTORY_SIZE)
        self._connections_lock = asyncio.Lock()
        self._publish_lock = asyncio.Lock()

    async def join(self, websocket: WebSocket, connection_id: str) -> int:
        # Sending the history snapshot under the publish lock guarantees that
        # the new client receives all later messages after its ready event.
        async with self._publish_lock:
            async with self._connections_lock:
                self._connections.add(websocket)
                history = list(self._history)
                online = len(self._connections)

            try:
                await websocket.send_json(
                    {
                        "type": "ready",
                        "connectionId": connection_id,
                        "online": online,
                        "history": history,
                    }
                )
            except Exception:
                async with self._connections_lock:
                    self._connections.discard(websocket)
                raise
            return online

    async def remove(self, websocket: WebSocket) -> tuple[bool, int]:
        async with self._connections_lock:
            was_connected = websocket in self._connections
            self._connections.discard(websocket)
            return was_connected, len(self._connections)

    async def online_count(self) -> int:
        async with self._connections_lock:
            return len(self._connections)

    async def publish_message(self, message: dict[str, Any]) -> None:
        # Keep the in-memory order consistent with the order messages are sent.
        async with self._publish_lock:
            self._history.append(message)
            await self.broadcast({"type": "message", "message": message})

    async def broadcast(
        self,
        event: dict[str, Any],
        *,
        exclude: set[WebSocket] | None = None,
    ) -> None:
        excluded = exclude or set()
        async with self._connections_lock:
            recipients = tuple(
                websocket
                for websocket in self._connections
                if websocket not in excluded
            )

        if not recipients:
            return

        results = await asyncio.gather(
            *(websocket.send_json(event) for websocket in recipients),
            return_exceptions=True,
        )
        failed = {
            websocket
            for websocket, result in zip(recipients, results)
            if isinstance(result, Exception)
        }
        if failed:
            async with self._connections_lock:
                self._connections.difference_update(failed)


manager = ConnectionManager()


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.get("/healthz")
async def health() -> dict[str, Any]:
    return {"status": "ok", "online": await manager.online_count()}


def clean_sender(value: Any) -> str:
    if not isinstance(value, str):
        return "匿名"
    sender = " ".join(value.split())[:MAX_NAME_LENGTH]
    return sender or "匿名"


async def send_error(websocket: WebSocket, detail: str) -> None:
    await websocket.send_json({"type": "error", "detail": detail})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connection_id = uuid.uuid4().hex
    try:
        online = await manager.join(websocket, connection_id)
    except Exception:
        return

    await manager.broadcast(
        {"type": "presence", "online": online},
        exclude={websocket},
    )

    try:
        while True:
            raw_event = await websocket.receive_text()
            try:
                event = json.loads(raw_event)
            except json.JSONDecodeError:
                await send_error(websocket, "消息格式无效。")
                continue

            if not isinstance(event, dict) or event.get("type") != "message":
                await send_error(websocket, "不支持的消息类型。")
                continue

            text = event.get("text")
            if not isinstance(text, str) or not text.strip():
                await send_error(websocket, "消息不能为空。")
                continue
            if len(text) > MAX_MESSAGE_LENGTH:
                await send_error(
                    websocket,
                    f"消息不能超过 {MAX_MESSAGE_LENGTH} 个字符。",
                )
                continue

            message = {
                "id": uuid.uuid4().hex,
                "sender": clean_sender(event.get("sender")),
                "senderId": connection_id,
                "text": text,
                "sentAt": datetime.now(timezone.utc).isoformat(
                    timespec="milliseconds"
                ),
            }
            await manager.publish_message(message)
    except WebSocketDisconnect:
        pass
    finally:
        was_connected, online = await manager.remove(websocket)
        if was_connected:
            await manager.broadcast({"type": "presence", "online": online})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )
