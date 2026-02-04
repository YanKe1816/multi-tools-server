import hashlib

from tests.asgi_client import request_json
from main import app


def _fingerprint(code: str) -> str:
    raw = f"schema_validate|validate|INPUT_INVALID|{code}|400"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def test_schema_validate_pass():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_validate",
        {"schema": {"type": "string"}, "data": "ok"},
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "schema_validate",
        "version": "1.0",
        "result": {"ok": True, "issues": [], "summary": {"issue_count": 0}},
        "error": None,
    }


def test_schema_validate_type_mismatch():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_validate",
        {"schema": {"type": "string"}, "data": 3},
    )
    assert status == 200
    assert body["result"]["ok"] is False
    assert body["result"]["issues"] == [
        {"path": "$", "code": "TYPE_MISMATCH", "message": "Expected string."}
    ]


def test_schema_validate_required_missing():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_validate",
        {
            "schema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            "data": {},
        },
    )
    assert status == 200
    assert body["result"]["issues"] == [
        {"path": "$.name", "code": "REQUIRED_MISSING", "message": "Required field missing."}
    ]


def test_schema_validate_additional_property():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_validate",
        {"schema": {"type": "object", "properties": {}}, "data": {"extra": 1}},
    )
    assert status == 200
    assert body["result"]["issues"] == [
        {
            "path": "$.extra",
            "code": "ADDITIONAL_PROPERTY",
            "message": "Additional property not allowed.",
        }
    ]


def test_schema_validate_invalid_schema():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_validate",
        {"schema": {"type": "string", "oneOf": []}, "data": "ok"},
    )
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "schema_validate",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "SCHEMA_UNSUPPORTED",
            "code": "SCHEMA_UNSUPPORTED",
            "message": "Unsupported schema keyword: oneOf.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "schema_validate", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": hashlib.sha256(
                "schema_validate|validate|SCHEMA_UNSUPPORTED|SCHEMA_UNSUPPORTED|400".encode("utf-8")
            ).hexdigest()[:16],
        },
    }


def test_schema_validate_malformed_request():
    status, body = request_json(app, "POST", "/tools/schema_validate", {"data": "ok"})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "schema_validate",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the schema_validate schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "schema_validate", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": _fingerprint("INPUT_INVALID"),
        },
    }
