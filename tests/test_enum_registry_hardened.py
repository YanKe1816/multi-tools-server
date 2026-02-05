from tests.asgi_client import request_json
from main import app


def test_enum_registry_known_enum():
    status, body = request_json(app, "POST", "/tools/enum_registry", {"name": "status"})
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "enum_registry",
        "version": "1.0",
        "result": {
            "enum": {
                "name": "status",
                "version": "1.0",
                "values": [
                    {"value": "OPEN", "label": "Open", "description": "Item is open."},
                    {"value": "CLOSED", "label": "Closed", "description": "Item is closed."},
                    {"value": "PENDING", "label": "Pending", "description": "Item is pending."},
                ],
            }
        },
        "error": None,
    }


def test_enum_registry_deterministic_order():
    status, body = request_json(app, "POST", "/tools/enum_registry", {"name": "status"})
    assert status == 200
    assert [item["value"] for item in body["result"]["enum"]["values"]] == ["OPEN", "CLOSED", "PENDING"]


def test_enum_registry_unknown_name():
    status, body = request_json(app, "POST", "/tools/enum_registry", {"name": "unknown"})
    assert status == 404
    assert body == {
        "ok": False,
        "tool": "enum_registry",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "NOT_FOUND",
            "code": "ENUM_UNKNOWN",
            "message": "Enum not found.",
            "retryable": False,
            "severity": "medium",
            "where": {"tool": "enum_registry", "stage": "lookup", "path": "name"},
            "http_status": 404,
            "fingerprint": "39ee62e64c457552",
        },
    }


def test_enum_registry_missing_name():
    status, body = request_json(app, "POST", "/tools/enum_registry", {})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "enum_registry",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the enum_registry schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "enum_registry", "stage": "lookup", "path": ""},
            "http_status": 400,
            "fingerprint": "6a6d5c90fabce822",
        },
    }


def test_enum_registry_malformed_request():
    status, body = request_json(app, "POST", "/tools/enum_registry", {"name": 123})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "enum_registry",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the enum_registry schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "enum_registry", "stage": "lookup", "path": ""},
            "http_status": 400,
            "fingerprint": "6a6d5c90fabce822",
        },
    }


def test_enum_registry_empty_name():
    status, body = request_json(app, "POST", "/tools/enum_registry", {"name": "  "})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "enum_registry",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "ENUM_INVALID",
            "message": "Enum name must be a non-empty string.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "enum_registry", "stage": "lookup", "path": "name"},
            "http_status": 400,
            "fingerprint": "c5d9bae19e29384e",
        },
    }
