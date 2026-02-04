from tests.asgi_client import request_json
from main import app


def test_schema_diff_identical():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_diff",
        {
            "old_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
            "new_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "schema_diff",
        "version": "1.0",
        "result": {"diff": {"added_fields": [], "removed_fields": [], "changed_fields": []}},
        "error": None,
    }


def test_schema_diff_field_added():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_diff",
        {
            "old_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
            "new_schema": {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}},
        },
    )
    assert status == 200
    assert body["result"]["diff"]["added_fields"] == [
        {"path": "age", "schema": {"type": "integer", "required": False, "enum": None}}
    ]
    assert body["result"]["diff"]["removed_fields"] == []
    assert body["result"]["diff"]["changed_fields"] == []


def test_schema_diff_field_removed():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_diff",
        {
            "old_schema": {"type": "object", "properties": {"age": {"type": "integer"}}},
            "new_schema": {"type": "object", "properties": {}},
        },
    )
    assert status == 200
    assert body["result"]["diff"]["removed_fields"] == [
        {"path": "age", "schema": {"type": "integer", "required": False, "enum": None}}
    ]
    assert body["result"]["diff"]["added_fields"] == []
    assert body["result"]["diff"]["changed_fields"] == []


def test_schema_diff_field_type_changed():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_diff",
        {
            "old_schema": {"type": "object", "properties": {"age": {"type": "string"}}},
            "new_schema": {"type": "object", "properties": {"age": {"type": "integer"}}},
        },
    )
    assert status == 200
    assert body["result"]["diff"]["changed_fields"] == [
        {
            "path": "age",
            "before": {"type": "string", "required": False, "enum": None, "detail": "type:string -> integer"},
            "after": {"type": "integer", "required": False, "enum": None, "detail": "type:string -> integer"},
        }
    ]


def test_schema_diff_malformed_request():
    status, body = request_json(app, "POST", "/tools/schema_diff", {"old_schema": "bad"})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "schema_diff",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the schema_diff schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "schema_diff", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "f64d49d9e07f3249",
        },
    }


def test_schema_diff_missing_schema():
    status, body = request_json(app, "POST", "/tools/schema_diff", {"new_schema": {}})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "schema_diff",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the schema_diff schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "schema_diff", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "f64d49d9e07f3249",
        },
    }


def test_schema_diff_unsupported_schema_feature():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_diff",
        {"old_schema": {"$ref": "#/defs/x"}, "new_schema": {"type": "object"}},
    )
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "schema_diff",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "SCHEMA_UNSUPPORTED",
            "code": "SCHEMA_UNSUPPORTED",
            "message": "ref is not supported",
            "retryable": False,
            "severity": "medium",
            "where": {"tool": "schema_diff", "stage": "validate", "path": "$ref"},
            "http_status": 400,
            "fingerprint": "cde10e367ba599d9",
        },
    }
