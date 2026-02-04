import asyncio
import json
from typing import Any, Tuple


def request_json(app, method: str, path: str, payload: Any | None = None) -> Tuple[int, Any]:
    return asyncio.run(_request_json(app, method, path, payload))


async def _request_json(app, method: str, path: str, payload: Any | None):
    body = b""
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

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
    response_body: list[bytes] = []

    async def receive():
        nonlocal body
        if body is None:
            return {"type": "http.request", "body": b"", "more_body": False}
        data = body
        body = None
        return {"type": "http.request", "body": data, "more_body": False}

    async def send(message):
        nonlocal response_status
        if message["type"] == "http.response.start":
            response_status = message["status"]
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    await app(scope, receive, send)
    parsed = json.loads(b"".join(response_body)) if response_body else None
    return response_status, parsed
