from tests.asgi_client import request_json
from main import app


def test_verify_test_simple_echo():
    status, body = request_json(app, "POST", "/tools/verify_test", {"text": "hello"})
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "verify_test",
        "version": "1.0",
        "result": {"echo": "hello", "length": 5},
        "error": None,
    }


def test_verify_test_length_deterministic():
    status, body = request_json(app, "POST", "/tools/verify_test", {"text": "abc"})
    assert status == 200
    assert body["result"]["length"] == 3
    assert body["result"]["echo"] == "abc"


def test_verify_test_repeat_same_input():
    payload = {"text": "repeat"}
    status_first, body_first = request_json(app, "POST", "/tools/verify_test", payload)
    status_second, body_second = request_json(app, "POST", "/tools/verify_test", payload)
    assert status_first == 200
    assert status_second == 200
    assert body_first == body_second


def test_verify_test_malformed_request():
    status, body = request_json(app, "POST", "/tools/verify_test", {"text": 123})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "verify_test",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the verify_test schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "verify_test", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "5fcbd1b6691af8f2",
        },
    }


def test_verify_test_missing_required_field():
    status, body = request_json(app, "POST", "/tools/verify_test", {})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "verify_test",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the verify_test schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "verify_test", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "5fcbd1b6691af8f2",
        },
    }


def test_verify_test_response_matches_contract():
    status, body = request_json(app, "POST", "/tools/verify_test", {"text": "contract"})
    assert status == 200
    assert set(body.keys()) == {"ok", "tool", "version", "result", "error"}
    assert set(body["result"].keys()) == {"echo", "length"}
