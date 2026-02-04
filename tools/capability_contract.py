from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StrictStr, ValidationError

router = APIRouter()


class Input(BaseModel):
    name: StrictStr

    class Config:
        extra = "forbid"


def _fingerprint(tool: str, stage: str, error_class: str, code: str, http_status: int) -> str:
    raw = f"{tool}|{stage}|{error_class}|{code}|{http_status}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _structured_error(
    code: str,
    message: str,
    http_status: int = 400,
    path: str = "",
    error_class: str = "INPUT_INVALID",
    stage: str = "validate",
) -> dict[str, Any]:
    return {
        "class": error_class,
        "code": code,
        "message": message,
        "retryable": False,
        "severity": "low" if error_class == "INPUT_INVALID" else "medium",
        "where": {"tool": "capability_contract", "stage": stage, "path": path},
        "http_status": http_status,
        "fingerprint": _fingerprint("capability_contract", stage, error_class, code, http_status),
    }


def _normalize_contract(contract: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(contract, sort_keys=True))


def _response(result: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "tool": "capability_contract", "version": "1.0", "result": result, "error": None}


@router.post("/tools/capability_contract")
def capability_contract(payload: dict[str, Any]):
    try:
        data = Input.model_validate(payload)
    except ValidationError:
        error = _structured_error("INPUT_INVALID", "Input must match the capability_contract schema.", stage="validate")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "capability_contract", "version": "1.0", "result": None, "error": error})

    name = data.name.strip()
    if not name:
        error = _structured_error("CAPABILITY_INVALID", "Capability name must be a non-empty string.", path="name", stage="validate")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "capability_contract", "version": "1.0", "result": None, "error": error})

    from tools._shared.contracts import CONTRACTS

    contract = CONTRACTS.get(name)
    if not contract:
        error = _structured_error("CAPABILITY_UNKNOWN", "Capability not found.", http_status=404, path="name", error_class="NOT_FOUND", stage="lookup")
        return JSONResponse(status_code=404, content={"ok": False, "tool": "capability_contract", "version": "1.0", "result": None, "error": error})

    return _response({"contract": _normalize_contract(contract)})


CONTRACT = {
    "name": "capability_contract",
    "version": "1.0.0",
    "path": "/tools/capability_contract",
    "description": "Return the declared contract metadata for a named capability.",
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
                    "properties": {"contract": {"type": "object"}},
                    "required": ["contract"],
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
            {"code": "CAPABILITY_UNKNOWN", "when": "capability not found"},
            {"code": "CAPABILITY_INVALID", "when": "capability name empty"},
            {"code": "INPUT_INVALID", "when": "request body invalid"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {
                "name": "text_normalize",
            },
            "output": {
                "ok": True,
                "tool": "capability_contract",
                "version": "1.0",
                "result": {"contract": {"name": "text_normalize"}},
                "error": None,
            },
        }
    ],
}
