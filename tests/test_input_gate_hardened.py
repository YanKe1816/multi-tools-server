from tests.asgi_client import request_json
from main import app


def test_input_gate_pass_simple():
    status, body = request_json(app, "POST", "/tools/input_gate", {"input": "ok"})
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "input_gate",
        "version": "1.0",
        "result": {"pass": True, "reasons": []},
        "error": None,
    }


def test_input_gate_string_too_long():
    status, body = request_json(
        app,
        "POST",
        "/tools/input_gate",
        {
            "input": "abcd",
            "rules": {
                "max_size": 1000,
                "allow_types": ["string"],
                "string": {"min_length": 0, "max_length": 3},
                "object": {"max_depth": 1, "max_keys": 1},
                "array": {"max_length": 1},
            },
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "input_gate",
        "version": "1.0",
        "result": {
            "pass": False,
            "reasons": [
                {"code": "STRING_TOO_LONG", "path": "$", "message": "String length exceeds max_length."}
            ],
        },
        "error": None,
    }


def test_input_gate_type_not_allowed():
    status, body = request_json(
        app,
        "POST",
        "/tools/input_gate",
        {
            "input": 5,
            "rules": {
                "max_size": 1000,
                "allow_types": ["string"],
                "string": {"min_length": 0, "max_length": 10},
                "object": {"max_depth": 1, "max_keys": 1},
                "array": {"max_length": 1},
            },
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "input_gate",
        "version": "1.0",
        "result": {
            "pass": False,
            "reasons": [{"code": "TYPE_NOT_ALLOWED", "path": "$", "message": "Input type is not allowed."}],
        },
        "error": None,
    }


def test_input_gate_object_too_deep():
    status, body = request_json(
        app,
        "POST",
        "/tools/input_gate",
        {
            "input": {"a": {"b": {"c": 1}}},
            "rules": {
                "max_size": 1000,
                "allow_types": ["object"],
                "string": {"min_length": 0, "max_length": 10},
                "object": {"max_depth": 2, "max_keys": 10},
                "array": {"max_length": 10},
            },
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "input_gate",
        "version": "1.0",
        "result": {
            "pass": False,
            "reasons": [
                {"code": "OBJECT_TOO_DEEP", "path": "$", "message": "Object depth exceeds max_depth."}
            ],
        },
        "error": None,
    }


def test_input_gate_invalid_rules():
    status, body = request_json(
        app,
        "POST",
        "/tools/input_gate",
        {
            "input": "ok",
            "rules": {
                "max_size": 0,
                "allow_types": ["string"],
                "string": {"min_length": 0, "max_length": 10},
                "object": {"max_depth": 1, "max_keys": 1},
                "array": {"max_length": 1},
            },
        },
    )
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "input_gate",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "RULES_INVALID",
            "message": "Rules are invalid.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "input_gate", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "586c289499b34f33",
        },
    }


def test_input_gate_malformed_request():
    status, body = request_json(app, "POST", "/tools/input_gate", {"rules": {}})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "input_gate",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the input_gate schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "input_gate", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "1cec0dab878b781e",
        },
    }
