import json

from tests.asgi_client import request_json
from main import app
from tools.text_normalize import CONTRACT as TEXT_NORMALIZE_CONTRACT


def test_capability_contract_fetch_known():
    status, body = request_json(app, "POST", "/tools/capability_contract", {"name": "text_normalize"})
    assert status == 200
    expected_contract = json.loads(json.dumps(TEXT_NORMALIZE_CONTRACT, sort_keys=True))
    assert body == {
        "ok": True,
        "tool": "capability_contract",
        "version": "1.0",
        "result": {"contract": expected_contract},
        "error": None,
    }


def test_capability_contract_deterministic():
    payload = {"name": "text_normalize"}
    status_first, body_first = request_json(app, "POST", "/tools/capability_contract", payload)
    status_second, body_second = request_json(app, "POST", "/tools/capability_contract", payload)
    assert status_first == 200
    assert status_second == 200
    assert body_first == body_second


def test_capability_contract_unknown_name():
    status, body = request_json(app, "POST", "/tools/capability_contract", {"name": "does_not_exist"})
    assert status == 404
    assert body == {
        "ok": False,
        "tool": "capability_contract",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "NOT_FOUND",
            "code": "CAPABILITY_UNKNOWN",
            "message": "Capability not found.",
            "retryable": False,
            "severity": "medium",
            "where": {"tool": "capability_contract", "stage": "lookup", "path": "name"},
            "http_status": 404,
            "fingerprint": "5281f018abaf5989",
        },
    }


def test_capability_contract_missing_name():
    status, body = request_json(app, "POST", "/tools/capability_contract", {})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "capability_contract",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the capability_contract schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "capability_contract", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "675cf938fd7e74be",
        },
    }


def test_capability_contract_malformed_request():
    status, body = request_json(app, "POST", "/tools/capability_contract", {"name": 123})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "capability_contract",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "INPUT_INVALID",
            "message": "Input must match the capability_contract schema.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "capability_contract", "stage": "validate", "path": ""},
            "http_status": 400,
            "fingerprint": "675cf938fd7e74be",
        },
    }


def test_capability_contract_empty_name():
    status, body = request_json(app, "POST", "/tools/capability_contract", {"name": "  "})
    assert status == 400
    assert body == {
        "ok": False,
        "tool": "capability_contract",
        "version": "1.0",
        "result": None,
        "error": {
            "class": "INPUT_INVALID",
            "code": "CAPABILITY_INVALID",
            "message": "Capability name must be a non-empty string.",
            "retryable": False,
            "severity": "low",
            "where": {"tool": "capability_contract", "stage": "validate", "path": "name"},
            "http_status": 400,
            "fingerprint": "c7647e3b7c17eef3",
        },
    }
