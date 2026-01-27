from tests.asgi_client import request_json
from main import app


def test_schema_map_strict_success():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_map",
        {
            "data": {"a": 1, "b": {"c": 2}, "drop": "bye"},
            "mapping": {
                "rename": {"b.c": "b.d", "a": "x"},
                "defaults": {"z": 9, "b.e": 5},
                "drop": ["drop"],
                "require": ["x", "b.d"],
            },
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "schema_map",
        "version": "1.0",
        "result": {
            "ok": True,
            "data": {"b": {"d": 2, "e": 5}, "x": 1, "z": 9},
            "meta": {"applied": ["rename:a->x", "rename:b.c->b.d", "defaults:b.e", "defaults:z", "drop:drop"]},
            "errors": [],
        },
        "error": None,
    }


def test_schema_map_strict_missing_paths():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_map",
        {
            "data": {"a": 1},
            "mapping": {"rename": {"missing": "x"}, "require": ["missing_required"]},
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "schema_map",
        "version": "1.0",
        "result": {
            "ok": False,
            "data": None,
            "meta": None,
            "errors": [
                {"path": "missing", "code": "SOURCE_PATH_MISSING", "message": "Rename source path is missing."},
                {"path": "missing_required", "code": "REQUIRED_MISSING", "message": "Required path is missing."},
            ],
        },
        "error": None,
    }


def test_schema_map_permissive_missing_paths():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_map",
        {
            "data": {"a": 1, "b": 2, "keep": 3},
            "mapping": {
                "rename": {"b": "c", "missing": "z", "a": "d"},
                "defaults": {"e": 5},
                "drop": ["keep"],
                "require": ["missing_required"],
            },
            "mode": "permissive",
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "schema_map",
        "version": "1.0",
        "result": {
            "ok": True,
            "data": {"c": 2, "d": 1, "e": 5},
            "meta": {"applied": ["rename:a->d", "rename:b->c", "defaults:e", "drop:keep"]},
            "errors": [
                {"path": "missing", "code": "SOURCE_PATH_MISSING", "message": "Rename source path is missing."},
                {"path": "missing_required", "code": "REQUIRED_MISSING", "message": "Required path is missing."},
            ],
        },
        "error": None,
    }


def test_schema_map_invalid_mode():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_map",
        {"data": {}, "mapping": {}, "mode": "invalid"},
    )
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "schema_map",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "MODE_INVALID",
            "message": "Mode must be strict or permissive.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "schema_map", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "3b1e2ff9e194a7bc",
        },
    }


def test_schema_map_invalid_path():
    status, body = request_json(
        app,
        "POST",
        "/tools/schema_map",
        {"data": {"a": 1}, "mapping": {"rename": {"a..b": "c"}}},
    )
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "schema_map",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "MAPPING_INVALID",
            "message": "Invalid path: a..b.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "schema_map", "stage": "validate", "path": "a..b"},
            "http_status": 400,
            "fingerprint": "7a392557836cbcc6",
        },
    }


def test_schema_map_invalid_payload():
    status, body = request_json(app, "POST", "/tools/schema_map", {"data": {"a": 1}})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "schema_map",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the schema_map schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "schema_map", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "b79e0b8cdc15e768",
        },
    }
