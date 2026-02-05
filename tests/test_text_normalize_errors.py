from tests.asgi_client import request_json
from main import app


def test_invalid_payload_shape():
    status, body = request_json(app, "POST", "/tools/text_normalize", {"ops": {"trim": True}})
    assert status == 400
    assert body["ok"] is False
    assert body["tool"] == "text_normalize"
    assert body["version"] == "1.0"
    assert body["result"] is None
    assert body["error"]["code"] == "INPUT_INVALID"


def test_invalid_ops_type():
    status, body = request_json(app, "POST", "/tools/text_normalize", {"text": "ok", "ops": {"trim": "yes"}})
    assert status == 400
    assert body["error"]["code"] == "INPUT_INVALID"
