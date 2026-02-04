from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StrictStr, ValidationError

router = APIRouter()

ENUM_REGISTRY: dict[str, dict[str, Any]] = {
    "status": {
        "name": "status",
        "version": "1.0",
        "values": [
            {"value": "OPEN", "label": "Open", "description": "Item is open."},
            {"value": "CLOSED", "label": "Closed", "description": "Item is closed."},
            {"value": "PENDING", "label": "Pending", "description": "Item is pending."},
        ],
    }
}


class Input(BaseModel):
    name: StrictStr

    class Config:
        extra = "forbid"


def _fingerprint(tool: str, stage: str, error_class: str, code: str, http_status: int) -> str:
    raw = f"{tool}|{stage}|{error_class}|{code}|{http_status}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _structured_error(code: str, message: str, http_status: int = 400, path: str = "", error_class: str = "INPUT_INVALID") -> dict[str, Any]:
    severity = "low" if error_class == "INPUT_INVALID" else "medium"
    return {
        "class": error_class,
        "code": code,
        "message": message,
        "retryable": False,
        "severity": severity,
        "where": {"tool": "enum_registry", "stage": "lookup", "path": path},
        "http_status": http_status,
        "fingerprint": _fingerprint("enum_registry", "lookup", error_class, code, http_status),
    }


def _response(result: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "tool": "enum_registry", "version": "1.0", "result": result, "error": None}


@router.post("/tools/enum_registry")
def enum_registry(payload: dict[str, Any]):
    try:
        data = Input.model_validate(payload)
    except ValidationError:
        error = _structured_error("INPUT_INVALID", "Input must match the enum_registry schema.", path="")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "enum_registry", "version": "1.0", "result": None, "error": error})

    name = data.name.strip()
    if not name:
        error = _structured_error("ENUM_INVALID", "Enum name must be a non-empty string.", path="name")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "enum_registry", "version": "1.0", "result": None, "error": error})

    enum_set = ENUM_REGISTRY.get(name)
    if not enum_set:
        error = _structured_error("ENUM_UNKNOWN", "Enum not found.", http_status=404, path="name", error_class="NOT_FOUND")
        return JSONResponse(status_code=404, content={"ok": False, "tool": "enum_registry", "version": "1.0", "result": None, "error": error})

    return _response({"enum": enum_set})


# Self-test hint (local):
# curl -X POST http://localhost:8000/tools/enum_registry/ \
#   -H "Content-Type: application/json" \
#   -d '{"name":"status"}'


CONTRACT = {
    "name": "enum_registry",
    "version": "1.0.0",
    "path": "/tools/enum_registry",
    "description": "Return a canonical enum value list for a named enum set.",
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
                "name": {"type": "string"},
            },
            "required": ["name"],
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
                        "enum": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "version": {"type": "string"},
                                "values": {"type": "array", "items": {"type": "object"}},
                            },
                            "required": ["name", "version", "values"],
                            "additionalProperties": False,
                        }
                    },
                    "required": ["enum"],
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
        "envelope": {
            "error": {
                "code": "string",
                "message": "string",
                "retryable": "boolean",
                "details": "object",
            }
        },
        "codes": [
            {"code": "ENUM_UNKNOWN", "when": "enum not found"},
            {"code": "ENUM_INVALID", "when": "enum name empty"},
            {"code": "INPUT_INVALID", "when": "request body invalid"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {
                "name": "status",
            },
            "output": {
                "ok": True,
                "tool": "enum_registry",
                "version": "1.0",
                "result": {"enum": {"name": "status", "version": "1.0", "values": [{"value": "OPEN"}]}},
                "error": None,
            },
        }
    ],
}
