from tests.asgi_client import request_json
from main import app


def test_verify_test_simple_echo():
    status, body = request_json(app, "POST", "/tools/verify_test", {"text": "hello"})
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "verify_test",
        "version": "1.0.0",
        "result": {
            "text": "hello",
            "length": 5,
            "sha256": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        },
    }


def test_verify_test_length_deterministic():
    status, body = request_json(app, "POST", "/tools/verify_test", {"text": "abc"})
    assert status == 200
    assert body["result"]["length"] == 3
    assert body["result"]["text"] == "abc"


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
        "error": {
            "code": "INPUT_INVALID",
            "message": "Input must match the verify_test schema.",
            "retryable": False,
            "details": {},
        }
    }


def test_verify_test_default_payload():
    status, body = request_json(app, "POST", "/tools/verify_test", {})
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "verify_test",
        "version": "1.0.0",
        "result": {
            "text": "",
            "length": 0,
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        },
    }


def test_verify_test_response_matches_contract():
    status, body = request_json(app, "POST", "/tools/verify_test", {"text": "contract"})
    assert status == 200
    assert set(body.keys()) == {"ok", "tool", "version", "result"}
    assert set(body["result"].keys()) == {"text", "length", "sha256"}


def test_verify_test_too_long():
    status, body = request_json(app, "POST", "/tools/verify_test", {"text": "abcd", "max_len": 3})
    assert status == 400
    assert body == {
        "error": {
            "code": "INPUT_TOO_LONG",
            "message": "Input text exceeds max_len.",
            "retryable": False,
            "details": {},
        }
    }
