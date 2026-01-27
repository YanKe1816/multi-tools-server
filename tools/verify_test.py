from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictStr, ValidationError

router = APIRouter()

TOOL_NAME = "verify_test"
TOOL_VERSION = "1.0"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: StrictStr


def _fingerprint(tool: str, stage: str, error_class: str, code: str, http_status: int) -> str:
    raw = f"{tool}|{stage}|{error_class}|{code}|{http_status}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _structured_error(code: str, message: str, http_status: int = 400, path: str = "") -> dict[str, Any]:
    error_class = "INPUT_INVALID"
    return {
        "class": error_class,
        "code": code,
        "message": message,
        "retryable": False,
        "severity": "low",
        "where": {"tool": TOOL_NAME, "stage": "validate", "path": path},
        "http_status": http_status,
        "fingerprint": _fingerprint(TOOL_NAME, "validate", error_class, code, http_status),
    }


def _response(result: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": result, "error": None}


@router.post("/tools/verify_test")
def verify_test(payload: dict[str, Any]):
    try:
        data = Input.model_validate(payload)
    except ValidationError:
        err = _structured_error("INPUT_INVALID", "Input must match the verify_test schema.")
        return JSONResponse(
            status_code=400,
            content={"ok": False, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": None, "error": err},
        )

    result = {"echo": data.text, "length": len(data.text)}
    return _response(result)


CONTRACT = {
    "name": "verify_test",
    "version": "1.0.0",
    "path": "/tools/verify_test",
    "description": "Echo input text and return its length for stability verification.",
    "determinism": {
        "same_input_same_output": True,
        "side_effects": False,
        "network": False,
        "storage": False,
    },
    "inputs": {
        "content_type": "application/json",
        "json_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    "outputs": {
        "content_type": "application/json",
        "json_schema": {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "version": {"type": "string"},
                "result": {
                    "type": ["object", "null"],
                    "properties": {"echo": {"type": "string"}, "length": {"type": "integer"}},
                    "required": ["echo", "length"],
                    "additionalProperties": False,
                },
                "error": {
                    "type": ["object", "null"],
                    "properties": {
                        "class": {"type": "string"},
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "retryable": {"type": "boolean"},
                        "severity": {"type": "string"},
                        "where": {
                            "type": "object",
                            "properties": {"tool": {"type": "string"}, "stage": {"type": "string"}, "path": {"type": "string"}},
                            "required": ["tool", "stage", "path"],
                            "additionalProperties": False,
                        },
                        "http_status": {"type": "integer"},
                        "fingerprint": {"type": "string"},
                    },
                    "required": ["class", "code", "message", "retryable", "severity", "where", "http_status", "fingerprint"],
                    "additionalProperties": False,
                },
            },
            "required": ["ok", "tool", "version", "result", "error"],
            "additionalProperties": False,
        },
    },
    "errors": {
        "envelope": {"error": {"code": "string", "message": "string", "retryable": "boolean", "details": "object"}},
        "codes": [{"code": "INPUT_INVALID", "when": "request body invalid"}],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {"text": "hello"},
            "output": {
                "ok": True,
                "tool": "verify_test",
                "version": "1.0",
                "result": {"echo": "hello", "length": 5},
                "error": None,
            },
        }
    ],
}
