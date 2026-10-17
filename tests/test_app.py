import asyncio
import json
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import websockets

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def running_server():
    port = free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    health_url = f"http://127.0.0.1:{port}/healthz"
    deadline = time.monotonic() + 10
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise RuntimeError(f"Uvicorn exited during startup:\n{output}")
            try:
                with urlopen(health_url, timeout=0.5) as response:
                    if response.status == 200:
                        break
            except (URLError, TimeoutError):
                time.sleep(0.05)
        else:
            raise RuntimeError("Uvicorn did not start within 10 seconds")

        yield f"http://127.0.0.1:{port}", f"ws://127.0.0.1:{port}/ws"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


async def receive_until(websocket, event_type: str):
    while True:
        event = json.loads(
            await asyncio.wait_for(websocket.recv(), timeout=2)
        )
        if event["type"] == event_type:
            return event


def test_index_and_health() -> None:
    with running_server() as (http_url, _):
        with urlopen(f"{http_url}/", timeout=2) as response:
            assert response.status == 200
            assert "局域网聊天室" in response.read().decode()

        with urlopen(f"{http_url}/healthz", timeout=2) as response:
            assert json.loads(response.read()) == {"status": "ok", "online": 0}


def test_messages_are_broadcast_and_replayed() -> None:
    with running_server() as (_, websocket_url):
        async def scenario():
            async with websockets.connect(websocket_url) as first:
                first_ready = await receive_until(first, "ready")
                assert first_ready["online"] == 1
                assert first_ready["history"] == []

                async with websockets.connect(websocket_url) as second:
                    second_ready = await receive_until(second, "ready")
                    assert second_ready["online"] == 2
                    assert second_ready["history"] == []

                    presence = await receive_until(first, "presence")
                    assert presence == {"type": "presence", "online": 2}

                    await second.send(
                        json.dumps(
                            {
                                "type": "message",
                                "sender": "  手机  用户  ",
                                "text": "  echo hello\n",
                            }
                        )
                    )

                    first_message = await receive_until(first, "message")
                    second_message = await receive_until(second, "message")
                    assert first_message == second_message
                    assert first_message["message"]["sender"] == "手机 用户"
                    assert first_message["message"]["text"] == "  echo hello\n"
                    assert (
                        first_message["message"]["senderId"]
                        == second_ready["connectionId"]
                    )
                    saved_message = first_message["message"]

            async with websockets.connect(websocket_url) as reconnected:
                ready = await receive_until(reconnected, "ready")
                assert ready["history"] == [saved_message]

        asyncio.run(scenario())


def test_empty_and_oversized_messages_are_rejected() -> None:
    with running_server() as (_, websocket_url):
        async def scenario():
            async with websockets.connect(websocket_url) as websocket:
                await receive_until(websocket, "ready")

                await websocket.send(
                    json.dumps(
                        {"type": "message", "sender": "电脑", "text": "   "}
                    )
                )
                error = await receive_until(websocket, "error")
                assert error["detail"] == "消息不能为空。"

                await websocket.send(
                    json.dumps(
                        {
                            "type": "message",
                            "sender": "电脑",
                            "text": "x" * 4001,
                        }
                    )
                )
                error = await receive_until(websocket, "error")
                assert "4000" in error["detail"]

        asyncio.run(scenario())
