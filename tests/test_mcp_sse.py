import asyncio
from typing import Any

from main import app
from tests.asgi_client import request_json


def test_connect_returns_fields():
    status, body = request_json(app, "GET", "/connect")
    assert status == 200
    assert body == {
        "server_name": "multi-tools-server",
        "server_version": "1.0.0",
        "sse_url": "/sse",
        "tools_url": "/mcp",
    }


def test_sse_content_type():
    status, headers, body = asyncio.run(_request_raw(app, "GET", "/sse"))
    assert status == 200
    content_type = headers.get("content-type", "")
    assert content_type.startswith("text/event-stream")
    assert body.startswith(b":" + (b" " * 2048))
    assert b"event: endpoint" in body


def test_message_invokes_verify_test():
    status, body = request_json(
        app,
        "POST",
        "/message",
        {"tool": "verify_test", "input": {"text": "ping"}, "request_id": "req-1"},
    )
    assert status == 200
    assert body["ok"] is True
    assert body["request_id"] == "req-1"
    assert body["tool"] == "verify_test"
    assert body["output"]["result"]["text"] == "ping"


async def _request_raw(app, method: str, path: str, payload: Any | None = None):
    body = b""
    if payload is not None:
        body = b"{}"

    headers = [(b"host", b"testserver")]
    if payload is not None:
        headers.append((b"content-type", b"application/json"))
        headers.append((b"content-length", str(len(body)).encode("utf-8")))

    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.1"},
        "method": method.upper(),
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers,
    }

    response_status = None
    response_headers: dict[str, str] = {}
    response_body: list[bytes] = []
    disconnect_event = asyncio.Event()

    async def receive():
        nonlocal body
        if body is None:
            if disconnect_event.is_set():
                return {"type": "http.disconnect"}
            await disconnect_event.wait()
            return {"type": "http.disconnect"}
        data = body
        body = None
        return {"type": "http.request", "body": data, "more_body": False}

    async def send(message):
        nonlocal response_status
        if message["type"] == "http.response.start":
            response_status = message["status"]
            response_headers.update({k.decode("utf-8"): v.decode("utf-8") for k, v in message.get("headers", [])})
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))
            disconnect_event.set()

    await app(scope, receive, send)
    return response_status, response_headers, b"".join(response_body)
