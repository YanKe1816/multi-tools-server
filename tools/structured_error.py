from __future__ import annotations

import hashlib
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

router = APIRouter()

TOOL_NAME = "structured_error"
TOOL_VERSION = "1.0"


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    stage: str
    version: str | None = ""


class ErrorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = ""
    message: str | None = ""
    type: str | None = ""
    http_status: int | None = 0
    path: str | None = ""
    details: dict[str, Any] = Field(default_factory=dict)


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_message_length: int = 300
    include_raw_message: bool = True


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Source
    error: Any
    policy: Policy


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


def _classify_error(code: str, http_status: int, message: str, error_type: str) -> str:
    code_upper = (code or "").upper()
    message_upper = (message or "").upper()
    type_upper = (error_type or "").upper()

    if code_upper.startswith("INPUT_"):
        return "INPUT_INVALID"
    if "RULES_" in code_upper:
        return "RULES_INVALID"
    if "SCHEMA_" in code_upper:
        return "SCHEMA_UNSUPPORTED"
    if http_status == 404 or "NOT_FOUND" in code_upper or "NOT FOUND" in message_upper:
        return "NOT_FOUND"
    if http_status == 429 or "RATE_LIMIT" in code_upper or "TOO MANY REQUESTS" in message_upper:
        return "RATE_LIMIT"
    if "TIMEOUT" in code_upper or "TIMEOUT" in message_upper or "TIMEOUT" in type_upper:
        return "TIMEOUT"
    if "UPSTREAM" in code_upper or http_status in (502, 503, 504):
        return "UPSTREAM"
    if "INTERNAL" in code_upper or http_status == 500:
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


def _extract_error(error_input: Any) -> ErrorInput:
    # allow: string | object | {"error": {...}} | already-normalized-ish
    if isinstance(error_input, str):
        return ErrorInput(code="", message=error_input, type="", http_status=0, path="", details={})

    if isinstance(error_input, dict):
        if "error" in error_input and isinstance(error_input["error"], dict):
            nested = error_input["error"]
            return ErrorInput(
                code=str(nested.get("code", "")),
                message=str(nested.get("message", "")),
                type=str(nested.get("type", "")),
                http_status=int(nested.get("http_status", 0) or 0),
                path=str(nested.get("path", "")),
                details=nested.get("details", {}) if isinstance(nested.get("details"), dict) else {},
            )

        return ErrorInput(
            code=str(error_input.get("code", "")),
            message=str(error_input.get("message", error_input.get("detail", ""))),
            type=str(error_input.get("type", "")),
            http_status=int(error_input.get("http_status", error_input.get("status", 0)) or 0),
            path=str(error_input.get("path", "")),
            details=error_input.get("details", {}) if isinstance(error_input.get("details"), dict) else {},
        )

    raise TypeError("error must be an object or string.")


@router.post("/tools/structured_error")
def structured_error(payload: dict[str, Any]):
    try:
        data = Input.model_validate(payload)
    except ValidationError:
        err = _structured_error("INPUT_INVALID", "Input must match the structured_error schema.", path="")
        return JSONResponse(
            status_code=400,
            content={"ok": False, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": None, "error": err},
        )

    policy = data.policy
    if not isinstance(policy.max_message_length, int) or not 1 <= policy.max_message_length <= 5000:
        err = _structured_error(
            "POLICY_INVALID",
            "policy.max_message_length must be an integer between 1 and 5000.",
            path="policy.max_message_length",
        )
        return JSONResponse(
            status_code=400,
            content={"ok": False, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": None, "error": err},
        )

    source = data.source
    if not isinstance(source.tool, str) or not source.tool.strip():
        err = _structured_error("SOURCE_INVALID", "source.tool must be a non-empty string.", path="source.tool")
        return JSONResponse(
            status_code=400,
            content={"ok": False, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": None, "error": err},
        )
    if not isinstance(source.stage, str) or not source.stage.strip():
        err = _structured_error("SOURCE_INVALID", "source.stage must be a non-empty string.", path="source.stage")
        return JSONResponse(
            status_code=400,
            content={"ok": False, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": None, "error": err},
        )

    try:
        error_input = _extract_error(data.error)
    except TypeError:
        err = _structured_error("ERROR_INVALID", "error must be an object or string.", path="error")
        return JSONResponse(
            status_code=400,
            content={"ok": False, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": None, "error": err},
        )

    raw_message = error_input.message or ""
    message = raw_message if policy.include_raw_message else ""
    if len(message) > policy.max_message_length:
        message = f"{message[:policy.max_message_length]}..."

    http_status = int(error_input.http_status or 0)
    error_type = error_input.type or ""
    code = (error_input.code or "").strip()

    error_class = _classify_error(code, http_status, raw_message, error_type)
    if not code:
        code = error_class

    normalized = {
        "class": error_class,
        "code": code,
        "message": message,
        "retryable": _retryable(error_class),
        "severity": _severity(error_class),
        "where": {"tool": source.tool, "stage": source.stage, "path": error_input.path or ""},
        "http_status": http_status,
        "fingerprint": _fingerprint(source.tool, source.stage, error_class, code, http_status),
    }

    return _response({"error": normalized})


CONTRACT: Dict[str, Any] = {
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
                "error": {"type": ["object", "string"]},
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
                "tool": {"type": "string"},
                "version": {"type": "string"},
                "result": {
                    "type": ["object", "null"],
                    "properties": {
                        "error": {
                            "type": "object",
                            "properties": {
                                "class": {"type": "string"},
                                "code": {"type": "string"},
                                "message": {"type": "string"},
                                "retryable": {"type": "boolean"},
                                "severity": {"type": "string"},
                                "where": {
                                    "type": "object",
                                    "properties": {
                                        "tool": {"type": "string"},
                                        "stage": {"type": "string"},
                                        "path": {"type": "string"},
                                    },
                                    "required": ["tool", "stage", "path"],
                                    "additionalProperties": False,
                                },
                                "http_status": {"type": "integer"},
                                "fingerprint": {"type": "string"},
                            },
                            "required": [
                                "class",
                                "code",
                                "message",
                                "retryable",
                                "severity",
                                "where",
                                "http_status",
                                "fingerprint",
                            ],
                            "additionalProperties": False,
                        }
                    },
                    "required": ["error"],
                    "additionalProperties": False,
                },
                "error": {"type": ["object", "null"]},
            },
            "required": ["ok", "tool", "version", "result", "error"],
            "additionalProperties": False,
        },
    },
    "errors": {
        "envelope": {
            "error": {"code": "string", "message": "string", "retryable": "boolean", "details": "object"}
        },
        "codes": [
            {"code": "POLICY_INVALID", "when": "policy fields invalid"},
            {"code": "SOURCE_INVALID", "when": "source fields invalid"},
            {"code": "ERROR_INVALID", "when": "error invalid"},
            {"code": "INPUT_INVALID", "when": "request body invalid"},
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
            "output": {
                "ok": True,
                "tool": "structured_error",
                "version": "1.0",
                "result": {
                    "error": {
                        "class": "RULES_INVALID",
                        "code": "RULES_INVALID",
                        "message": "bad",
                        "retryable": False,
                        "severity": "low",
                        "where": {"tool": "x", "stage": "y", "path": ""},
                        "http_status": 400,
                        "fingerprint": "example",
                    }
                },
                "error": None,
            },
        }
    ],
}
