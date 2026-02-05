from tests.asgi_client import request_json
from main import app


def test_identity_no_ops():
    status, body = request_json(app, "POST", "/tools/text_normalize", {"text": "Hello"})
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "text_normalize",
        "version": "1.0",
        "result": {
            "text": "Hello",
            "meta": {"original_length": 5, "normalized_length": 5, "applied": []},
        },
        "error": None,
    }


def test_trim_and_collapse_whitespace():
    status, body = request_json(
        app,
        "POST",
        "/tools/text_normalize",
        {"text": "  Hello   World  ", "ops": {"trim": True, "collapse_whitespace": True}},
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "text_normalize",
        "version": "1.0",
        "result": {
            "text": "Hello World",
            "meta": {"original_length": 17, "normalized_length": 11, "applied": ["collapse_whitespace", "trim"]},
        },
        "error": None,
    }


def test_normalize_newlines():
    status, body = request_json(
        app,
        "POST",
        "/tools/text_normalize",
        {"text": "a\r\nb\rc", "ops": {"normalize_newlines": True}},
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "text_normalize",
        "version": "1.0",
        "result": {
            "text": "a\nb\nc",
            "meta": {"original_length": 6, "normalized_length": 5, "applied": ["normalize_newlines"]},
        },
        "error": None,
    }


def test_to_lower():
    status, body = request_json(
        app,
        "POST",
        "/tools/text_normalize",
        {"text": "MiX", "ops": {"to_lower": True}},
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "text_normalize",
        "version": "1.0",
        "result": {
            "text": "mix",
            "meta": {"original_length": 3, "normalized_length": 3, "applied": ["to_lower"]},
        },
        "error": None,
    }


def test_remove_control_chars_preserve_tabs_newlines():
    status, body = request_json(
        app,
        "POST",
        "/tools/text_normalize",
        {"text": "a\x01\tb\n\x02c", "ops": {"remove_control_chars": True}},
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "text_normalize",
        "version": "1.0",
        "result": {
            "text": "a\tb\nc",
            "meta": {"original_length": 7, "normalized_length": 5, "applied": ["remove_control_chars"]},
        },
        "error": None,
    }


def test_invalid_text_type():
    status, body = request_json(app, "POST", "/tools/text_normalize", {"text": 123})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "text_normalize",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the text_normalize schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "text_normalize", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "6949dfdd6bbc64d3",
        },
    }
