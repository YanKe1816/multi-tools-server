import json
import asyncio
from typing import Any

from main import app
from tests.asgi_client import request_json


def test_sse_content_type_and_endpoint_event():
    status, headers, body = asyncio.run(_request_raw(app, "GET", "/sse"))
    assert status == 200
    assert headers.get("content-type", "").startswith("text/event-stream")
    assert body.startswith(b":" + (b" " * 2048))
    assert b"event: endpoint" in body
    assert b"data: http://testserver/message" in body


def test_message_jsonrpc_initialize_echoes_protocol_version():
    status, body = request_json(
        app,
        "POST",
        "/message",
        {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "x", "version": "0"},
            },
        },
    )
    assert status == 200
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "1"
    assert body["result"]["protocolVersion"] == "2025-03-26"
    assert body["result"]["serverInfo"]["name"] == "multi-tools-server"


def test_message_jsonrpc_initialize_uses_default_protocol_version_when_missing():
    status, body = request_json(
        app,
        "POST",
        "/message",
        {"jsonrpc": "2.0", "id": "1", "method": "initialize", "params": {}},
    )
    assert status == 200
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "1"
    assert body["result"]["protocolVersion"] == "2025-03-26"
    assert body["result"]["serverInfo"]["name"] == "multi-tools-server"


def test_message_jsonrpc_notification_initialized_without_id_returns_result_null():
    status, body = request_json(
        app,
        "POST",
        "/message",
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
    )
    assert status == 200
    assert body == {"jsonrpc": "2.0", "result": None}


def test_message_jsonrpc_notification_initialized_with_id_returns_result_null():
    status, body = request_json(
        app,
        "POST",
        "/message",
        {"jsonrpc": "2.0", "id": "n1", "method": "notifications/initialized", "params": {}},
    )
    assert status == 200
    assert body == {"jsonrpc": "2.0", "id": "n1", "result": None}

def test_sse_post_bridge_initialize_includes_protocol_version():
    status, body = request_json(
        app,
        "POST",
        "/sse/",
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "x", "version": "0"},
            },
        },
    )
    assert status == 200
    assert body["result"]["protocolVersion"] == "2025-03-26"

def test_message_jsonrpc_tools_list():
    status, body = request_json(
        app,
        "POST",
        "/message",
        {"jsonrpc": "2.0", "id": "2", "method": "tools/list", "params": {}},
    )
    assert status == 200
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "2"
    tools = body["result"]["tools"]
    assert any(tool["name"] == "verify_test" for tool in tools)
    verify_tool = next(tool for tool in tools if tool["name"] == "verify_test")
    assert set(verify_tool.keys()) == {"name", "description", "inputSchema"}


def test_message_jsonrpc_tools_call_verify_test():
    status, body = request_json(
        app,
        "POST",
        "/message",
        {
            "jsonrpc": "2.0",
            "id": "3",
            "method": "tools/call",
            "params": {"name": "verify_test", "arguments": {"text": "ping"}},
        },
    )
    assert status == 200
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "3"
    content = body["result"]["content"]
    assert content[0]["type"] == "text"
    payload = json.loads(content[0]["text"])
    assert payload["result"]["text"] == "ping"


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
