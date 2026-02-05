from tests.asgi_client import request_json
from main import app


def test_structured_error_normalize_simple():
    status, body = request_json(
        app,
        "POST",
        "/tools/structured_error",
        {
            "source": {"tool": "client", "stage": "parse", "version": "1.0"},
            "error": {"code": "INPUT_INVALID", "message": "bad input", "http_status": 400, "path": "$.x"},
            "policy": {"max_message_length": 300, "include_raw_message": True},
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "structured_error",
        "version": "1.0",
        "result": {
            "error": {
                "class": "INPUT_INVALID",
                "code": "INPUT_INVALID",
                "message": "bad input",
                "retryable": False,
                "severity": "low",
                "where": {"tool": "client", "stage": "parse", "path": "$.x"},
                "http_status": 400,
                "fingerprint": "3b26ba97a5cb0ac9",
            }
        },
        "error": None,
    }


def test_structured_error_normalize_exception_dict():
    status, body = request_json(
        app,
        "POST",
        "/tools/structured_error",
        {
            "source": {"tool": "svc", "stage": "call", "version": "1.0"},
            "error": {"type": "TimeoutError", "message": "request timeout"},
            "policy": {"max_message_length": 300, "include_raw_message": True},
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "structured_error",
        "version": "1.0",
        "result": {
            "error": {
                "class": "TIMEOUT",
                "code": "TIMEOUT",
                "message": "request timeout",
                "retryable": True,
                "severity": "medium",
                "where": {"tool": "svc", "stage": "call", "path": ""},
                "http_status": 0,
                "fingerprint": "a8b613799faaee93",
            }
        },
        "error": None,
    }


def test_structured_error_known_pattern_schema():
    status, body = request_json(
        app,
        "POST",
        "/tools/structured_error",
        {
            "source": {"tool": "svc", "stage": "validate", "version": "1.0"},
            "error": {"code": "SCHEMA_INVALID", "message": "bad schema", "http_status": 400},
            "policy": {"max_message_length": 300, "include_raw_message": True},
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "structured_error",
        "version": "1.0",
        "result": {
            "error": {
                "class": "SCHEMA_UNSUPPORTED",
                "code": "SCHEMA_INVALID",
                "message": "bad schema",
                "retryable": False,
                "severity": "low",
                "where": {"tool": "svc", "stage": "validate", "path": ""},
                "http_status": 400,
                "fingerprint": "85ba2fb187cdba8d",
            }
        },
        "error": None,
    }


def test_structured_error_unknown_input():
    status, body = request_json(
        app,
        "POST",
        "/tools/structured_error",
        {
            "source": {"tool": "svc", "stage": "run", "version": "1.0"},
            "error": "something odd happened",
            "policy": {"max_message_length": 300, "include_raw_message": True},
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "structured_error",
        "version": "1.0",
        "result": {
            "error": {
                "class": "UNKNOWN",
                "code": "UNKNOWN",
                "message": "something odd happened",
                "retryable": False,
                "severity": "medium",
                "where": {"tool": "svc", "stage": "run", "path": ""},
                "http_status": 0,
                "fingerprint": "912c949e524b8139",
            }
        },
        "error": None,
    }


def test_structured_error_malformed_request():
    status, body = request_json(
        app,
        "POST",
        "/tools/structured_error",
        {
            "source": {"tool": "svc", "stage": "run", "version": "1.0"},
            "error": ["not", "supported"],
            "policy": {"max_message_length": 300, "include_raw_message": True},
        },
    )
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "structured_error",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "ERROR_INVALID",
            "message": "error must be an object or string.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "structured_error", "stage": "validate", "path": "error"},
            "http_status": 400,
            "fingerprint": "3328bfc6a75e0493",
        },
    }


def test_structured_error_missing_required_fields():
    status, body = request_json(
        app,
        "POST",
        "/tools/structured_error",
        {"source": {"tool": "svc", "stage": "run", "version": "1.0"}, "error": {"code": "INPUT_INVALID"}},
    )
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "structured_error",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the structured_error schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "structured_error", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "5ec20af2b445b247",
        },
    }
