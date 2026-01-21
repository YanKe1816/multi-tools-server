from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


class Source(BaseModel):
    tool: str
    stage: str
    version: str | None = ""


class ErrorInput(BaseModel):
    code: str
    message: str
    type: str | None = ""
    http_status: int | None = 0
    path: str | None = ""
    details: dict[str, Any] = {}


class Policy(BaseModel):
    max_message_length: int = 300
    include_raw_message: bool = True


class Input(BaseModel):
    source: Source
    error: ErrorInput
    policy: Policy


def _classify_error(code: str, http_status: int) -> str:
    if code.startswith("INPUT_"):
        return "INPUT_INVALID"
    if "RULES_" in code:
        return "RULES_INVALID"
    if "SCHEMA_" in code:
        return "SCHEMA_UNSUPPORTED"
    if http_status == 404 or "NOT_FOUND" in code:
        return "NOT_FOUND"
    if http_status == 429 or "RATE_LIMIT" in code:
        return "RATE_LIMIT"
    if "TIMEOUT" in code:
        return "TIMEOUT"
    if "UPSTREAM" in code or http_status in (502, 503, 504):
        return "UPSTREAM"
    if "INTERNAL" in code or http_status == 500:
        return "INTERNAL"
    return "UNKNOWN"


def _retryable(error_class: str) -> bool:
    return error_class in {"RATE_LIMIT", "TIMEOUT", "UPSTREAM"}


def _severity(error_class: str) -> str:
    if error_class in {"INPUT_INVALID", "RULES_INVALID", "SCHEMA_UNSUPPORTED"}:
        return "low"
    if error_class in {"RATE_LIMIT", "TIMEOUT", "UPSTREAM"}:
        return "medium"
    if error_class == "INTERNAL":
        return "high"
    return "medium"


def _fingerprint(tool: str, stage: str, error_class: str, code: str, http_status: int) -> str:
    raw = f"{tool}|{stage}|{error_class}|{code}|{http_status}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@router.post("/tools/structured_error")
def structured_error(payload: Input):
    policy = payload.policy
    if not isinstance(policy.max_message_length, int) or not 1 <= policy.max_message_length <= 5000:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "POLICY_INVALID",
                    "message": "policy.max_message_length must be an integer between 1 and 5000.",
                }
            },
        )
    if not isinstance(policy.include_raw_message, bool):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "POLICY_INVALID",
                    "message": "policy.include_raw_message must be a boolean.",
                }
            },
        )

    source = payload.source
    if not isinstance(source.tool, str) or not source.tool.strip():
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "SOURCE_INVALID",
                    "message": "source.tool must be a non-empty string.",
                }
            },
        )
    if not isinstance(source.stage, str) or not source.stage.strip():
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "SOURCE_INVALID",
                    "message": "source.stage must be a non-empty string.",
                }
            },
        )

    error = payload.error
    if not isinstance(error.code, str) or not error.code.strip():
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "ERROR_INVALID",
                    "message": "error.code must be a non-empty string.",
                }
            },
        )

    http_status = error.http_status or 0
    error_class = _classify_error(error.code, http_status)
    retryable = _retryable(error_class)
    severity = _severity(error_class)

    message = error.message if policy.include_raw_message else ""
    if len(message) > policy.max_message_length:
        message = f"{message[:policy.max_message_length]}..."

    tool = source.tool
    stage = source.stage
    path = error.path or ""

    return {
        "ok": False,
        "error": {
            "class": error_class,
            "code": error.code,
            "message": message,
            "retryable": retryable,
            "severity": severity,
            "where": {"tool": tool, "stage": stage, "path": path},
            "http_status": http_status,
            "fingerprint": _fingerprint(tool, stage, error_class, error.code, http_status),
        },
    }


CONTRACT = {
    "name": "structured_error",
    "version": "1.0.0",
    "path": "/tools/structured_error",
    "description": "Normalize error inputs into a structured error envelope.",
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
            "properties": {
                "source": {"type": "object"},
                "error": {"type": "object"},
                "policy": {"type": "object"},
            },
            "required": ["source", "error", "policy"],
            "additionalProperties": False,
        },
    },
    "outputs": {
        "content_type": "application/json",
        "json_schema": {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "error": {"type": "object"},
            },
            "required": ["ok", "error"],
            "additionalProperties": False,
        },
    },
    "errors": {
        "envelope": {
            "error": {
                "code": "string",
                "message": "string",
                "retryable": "boolean",
                "details": "object",
            }
        },
        "codes": [
            {"code": "POLICY_INVALID", "when": "policy fields invalid"},
            {"code": "SOURCE_INVALID", "when": "source fields invalid"},
            {"code": "ERROR_INVALID", "when": "error.code missing"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {
                "source": {"tool": "x", "stage": "y", "version": "1"},
                "error": {"code": "RULES_INVALID", "message": "bad", "http_status": 400},
                "policy": {"max_message_length": 300, "include_raw_message": True},
            },
            "output": {"ok": False, "error": {"class": "RULES_INVALID", "code": "RULES_INVALID"}},
        }
    ],
}
