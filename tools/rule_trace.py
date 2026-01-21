from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictBool, StrictInt, StrictStr, ValidationError

router = APIRouter()


class Summary(BaseModel):
    type: StrictStr
    size: StrictInt
    hash: StrictStr

    class Config:
        extra = "forbid"


class Rule(BaseModel):
    rule_id: StrictStr
    type: StrictStr
    path: StrictStr
    matched: StrictBool
    reason: StrictStr

    class Config:
        extra = "forbid"


class InputPayload(BaseModel):
    summary: Summary

    class Config:
        extra = "forbid"


class Result(BaseModel):
    ok: StrictBool
    output_summary: Summary | None = None

    class Config:
        extra = "forbid"


class Payload(BaseModel):
    rules: list[Rule]
    input: InputPayload
    result: Result

    class Config:
        extra = "forbid"


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
        "where": {"tool": "rule_trace", "stage": "validate", "path": path},
        "http_status": http_status,
        "fingerprint": _fingerprint("rule_trace", "validate", error_class, code, http_status),
    }


def _response(result: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "tool": "rule_trace", "version": "1.0", "result": result, "error": None}


@router.post("/tools/rule_trace")
def rule_trace(payload: dict[str, Any]):
    try:
        data = Payload.model_validate(payload)
    except ValidationError:
        error = _structured_error("INPUT_INVALID", "Input must match the rule_trace schema.")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "rule_trace", "version": "1.0", "result": None, "error": error})

    allowed_types = {"allow", "reject", "note"}
    for index, rule in enumerate(data.rules):
        if rule.type not in allowed_types:
            error = _structured_error("RULE_TYPE_UNSUPPORTED", "Rule type is not supported.", path=f"rules[{index}].type")
            return JSONResponse(status_code=400, content={"ok": False, "tool": "rule_trace", "version": "1.0", "result": None, "error": error})

    matched_rules = []
    skipped_rules = []
    for rule in data.rules:
        record = {
            "rule_id": rule.rule_id,
            "type": rule.type,
            "path": rule.path,
            "reason": rule.reason,
        }
        if rule.matched:
            matched_rules.append(record)
        else:
            skipped_rules.append(record)

    output_summary = data.result.output_summary
    trace = {
        "input": {
            "type": data.input.summary.type,
            "size": data.input.summary.size,
            "hash": data.input.summary.hash,
        },
        "output": {
            "type": output_summary.type if output_summary else "",
            "size": output_summary.size if output_summary else 0,
            "hash": output_summary.hash if output_summary else "",
        },
        "matched_rules": matched_rules,
        "skipped_rules": skipped_rules,
        "summary": {
            "result_ok": data.result.ok,
            "matched_count": len(matched_rules),
            "skipped_count": len(skipped_rules),
        },
    }

    return _response({"trace": trace})


CONTRACT = {
    "name": "rule_trace",
    "version": "1.0.0",
    "path": "/tools/rule_trace",
    "description": "Normalize execution traces with input/output summaries and rule hits.",
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
                "rules": {"type": "array", "items": {"type": "object"}},
                "input": {"type": "object"},
                "result": {"type": "object"},
            },
            "required": ["rules", "input", "result"],
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
                        "trace": {
                            "type": "object",
                            "properties": {
                                "input": {"type": "object"},
                                "output": {"type": "object"},
                                "matched_rules": {"type": "array", "items": {"type": "object"}},
                                "skipped_rules": {"type": "array", "items": {"type": "object"}},
                                "summary": {"type": "object"},
                            },
                            "required": ["input", "output", "matched_rules", "skipped_rules", "summary"],
                            "additionalProperties": False,
                        }
                    },
                    "required": ["trace"],
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
            {"code": "RULE_TYPE_UNSUPPORTED", "when": "rule type not supported"},
            {"code": "INPUT_INVALID", "when": "request body invalid"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {
                "rules": [{"rule_id": "r1", "type": "allow", "path": "$", "matched": True, "reason": "ok"}],
                "input": {"summary": {"type": "string", "size": 1, "hash": "h"}},
                "result": {"ok": True, "output_summary": {"type": "string", "size": 1, "hash": "h"}},
            },
            "output": {
                "ok": True,
                "tool": "rule_trace",
                "version": "1.0",
                "result": {
                    "trace": {
                        "input": {"type": "string"},
                        "output": {"type": "string"},
                        "matched_rules": [],
                        "skipped_rules": [],
                        "summary": {"result_ok": True},
                    }
                },
                "error": None,
            },
        }
    ],
}
