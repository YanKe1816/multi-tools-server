from tests.asgi_client import request_json
from main import app


def test_rule_trace_simple_match():
    status, body = request_json(
        app,
        "POST",
        "/tools/rule_trace",
        {
            "rules": [{"rule_id": "r1", "type": "allow", "path": "$.a", "matched": True, "reason": "ok"}],
            "input": {"summary": {"type": "object", "size": 1, "hash": "h1"}},
            "result": {"ok": True, "output_summary": {"type": "object", "size": 1, "hash": "h2"}},
        },
    )
    assert status == 200
    assert body == {
        "ok": True,
        "tool": "rule_trace",
        "version": "1.0",
        "result": {
            "trace": {
                "input": {"type": "object", "size": 1, "hash": "h1"},
                "output": {"type": "object", "size": 1, "hash": "h2"},
                "matched_rules": [{"rule_id": "r1", "type": "allow", "path": "$.a", "reason": "ok"}],
                "skipped_rules": [],
                "summary": {"result_ok": True, "matched_count": 1, "skipped_count": 0},
            }
        },
        "error": None,
    }


def test_rule_trace_ordering_multiple_rules():
    status, body = request_json(
        app,
        "POST",
        "/tools/rule_trace",
        {
            "rules": [
                {"rule_id": "r1", "type": "note", "path": "$.a", "matched": False, "reason": "skip"},
                {"rule_id": "r2", "type": "reject", "path": "$.b", "matched": True, "reason": "blocked"},
                {"rule_id": "r3", "type": "allow", "path": "$.c", "matched": True, "reason": "ok"},
            ],
            "input": {"summary": {"type": "object", "size": 2, "hash": "h1"}},
            "result": {"ok": False, "output_summary": {"type": "object", "size": 0, "hash": ""}},
        },
    )
    assert status == 200
    assert body["result"]["trace"]["matched_rules"] == [
        {"rule_id": "r2", "type": "reject", "path": "$.b", "reason": "blocked"},
        {"rule_id": "r3", "type": "allow", "path": "$.c", "reason": "ok"},
    ]
    assert body["result"]["trace"]["skipped_rules"] == [
        {"rule_id": "r1", "type": "note", "path": "$.a", "reason": "skip"}
    ]


def test_rule_trace_no_match_summary():
    status, body = request_json(
        app,
        "POST",
        "/tools/rule_trace",
        {
            "rules": [{"rule_id": "r1", "type": "allow", "path": "$", "matched": False, "reason": "nope"}],
            "input": {"summary": {"type": "string", "size": 1, "hash": "h1"}},
            "result": {"ok": True, "output_summary": {"type": "string", "size": 1, "hash": "h2"}},
        },
    )
    assert status == 200
    assert body["result"]["trace"]["matched_rules"] == []
    assert body["result"]["trace"]["summary"] == {"result_ok": True, "matched_count": 0, "skipped_count": 1}


def test_rule_trace_malformed_request():
    status, body = request_json(app, "POST", "/tools/rule_trace", {"rules": "bad"})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "rule_trace",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the rule_trace schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "rule_trace", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "15de930a41319a0c",
        },
    }


def test_rule_trace_missing_required_fields():
    status, body = request_json(app, "POST", "/tools/rule_trace", {})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "rule_trace",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the rule_trace schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "rule_trace", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "15de930a41319a0c",
        },
    }


def test_rule_trace_unsupported_rule_type():
    status, body = request_json(
        app,
        "POST",
        "/tools/rule_trace",
        {
            "rules": [{"rule_id": "r1", "type": "ban", "path": "$", "matched": True, "reason": "no"}],
            "input": {"summary": {"type": "string", "size": 1, "hash": "h1"}},
            "result": {"ok": True, "output_summary": {"type": "string", "size": 1, "hash": "h2"}},
        },
    )
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "rule_trace",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "RULE_TYPE_UNSUPPORTED",
            "message": "Rule type is not supported.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "rule_trace", "stage": "validate", "path": "rules[0].type"},
            "http_status": 400,
            "fingerprint": "a8bbaf7f2488cea2",
        },
    }
