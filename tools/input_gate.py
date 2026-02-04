from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictStr, ValidationError

router = APIRouter()

DEFAULT_RULES = {
    "max_size": 10000,
    "allow_types": ["object", "array", "string", "number", "boolean", "null"],
    "string": {"min_length": 0, "max_length": 2000},
    "object": {"max_depth": 8, "max_keys": 100},
    "array": {"max_length": 200},
}


class Input(BaseModel):
    input: Any
    rules: dict[str, Any] | None = None
    mode: StrictStr = "strict"

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
        "where": {"tool": "input_gate", "stage": "validate", "path": path},
        "http_status": http_status,
        "fingerprint": _fingerprint("input_gate", "validate", error_class, code, http_status),
    }


def _merge_rules(overrides: dict[str, Any] | None) -> dict[str, Any]:
    merged = {
        "max_size": DEFAULT_RULES["max_size"],
        "allow_types": list(DEFAULT_RULES["allow_types"]),
        "string": dict(DEFAULT_RULES["string"]),
        "object": dict(DEFAULT_RULES["object"]),
        "array": dict(DEFAULT_RULES["array"]),
    }
    if not overrides:
        return merged

    for key in ("max_size", "allow_types"):
        if key in overrides:
            merged[key] = overrides[key]
    for key in ("string", "object", "array"):
        if key in overrides and isinstance(overrides[key], dict):
            merged[key].update(overrides[key])
    return merged


def _rules_valid(rules: dict[str, Any]) -> bool:
    allowed_types = {"object", "array", "string", "number", "boolean", "null"}
    if not isinstance(rules.get("max_size"), (int, float)):
        return False
    allow_types = rules.get("allow_types")
    if not isinstance(allow_types, list) or not allow_types:
        return False
    if not all(isinstance(item, str) and item in allowed_types for item in allow_types):
        return False
    string_rules = rules.get("string")
    object_rules = rules.get("object")
    array_rules = rules.get("array")
    if not isinstance(string_rules, dict) or not isinstance(object_rules, dict) or not isinstance(array_rules, dict):
        return False
    if not isinstance(string_rules.get("min_length"), (int, float)):
        return False
    if not isinstance(string_rules.get("max_length"), (int, float)):
        return False
    if not isinstance(object_rules.get("max_depth"), (int, float)):
        return False
    if not isinstance(object_rules.get("max_keys"), (int, float)):
        return False
    if not isinstance(array_rules.get("max_length"), (int, float)):
        return False
    if rules.get("max_size") <= 0:
        return False
    return True


def _json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False))


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    return "unknown"


def _object_depth(value: Any, current: int = 0) -> int:
    if isinstance(value, dict):
        depth = current + 1
        max_child = depth
        for child in value.values():
            max_child = max(max_child, _object_depth(child, depth))
        return max_child
    if isinstance(value, list):
        max_child = current
        for item in value:
            max_child = max(max_child, _object_depth(item, current))
        return max_child
    return current


def _max_object_keys(value: Any) -> int:
    if isinstance(value, dict):
        max_keys = len(value)
        for child in value.values():
            max_keys = max(max_keys, _max_object_keys(child))
        return max_keys
    if isinstance(value, list):
        max_keys = 0
        for item in value:
            max_keys = max(max_keys, _max_object_keys(item))
        return max_keys
    return 0


def _sorted_reasons(reasons: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(reasons, key=lambda item: (item["code"], item["path"], item["message"]))


@router.post("/tools/input_gate")
def input_gate(payload: dict[str, Any]):
    try:
        data = Input.model_validate(payload)
    except ValidationError:
        error = _structured_error("INPUT_INVALID", "Input must match the input_gate schema.")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "input_gate", "version": "1.0", "result": None, "error": error})

    if data.mode not in {"strict", "permissive"}:
        error = _structured_error("MODE_INVALID", "Mode must be strict or permissive.")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "input_gate", "version": "1.0", "result": None, "error": error})

    rules = _merge_rules(data.rules)
    if not _rules_valid(rules):
        error = _structured_error("RULES_INVALID", "Rules are invalid.")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "input_gate", "version": "1.0", "result": None, "error": error})

    reasons: list[dict[str, str]] = []
    strict = data.mode == "strict"

    def add_reason(code: str, path: str, message: str) -> bool:
        reasons.append({"code": code, "path": path, "message": message})
        return strict

    value = data.input
    value_type = _type_name(value)
    if value_type == "unknown" or value_type not in rules["allow_types"]:
        if add_reason("TYPE_NOT_ALLOWED", "$", "Input type is not allowed."):
            return {
                "ok": True,
                "tool": "input_gate",
                "version": "1.0",
                "result": {"pass": False, "reasons": _sorted_reasons(reasons)},
                "error": None,
            }

    if _json_size(value) > rules["max_size"]:
        if add_reason("JSON_TOO_LARGE", "$", "JSON size exceeds max_size."):
            return {
                "ok": True,
                "tool": "input_gate",
                "version": "1.0",
                "result": {"pass": False, "reasons": _sorted_reasons(reasons)},
                "error": None,
            }

    if value_type == "string":
        length = len(value)
        if length < rules["string"]["min_length"]:
            if add_reason("STRING_TOO_SHORT", "$", "String length is below min_length."):
                return {
                    "ok": True,
                    "tool": "input_gate",
                    "version": "1.0",
                    "result": {"pass": False, "reasons": _sorted_reasons(reasons)},
                    "error": None,
                }
        if length > rules["string"]["max_length"]:
            if add_reason("STRING_TOO_LONG", "$", "String length exceeds max_length."):
                return {
                    "ok": True,
                    "tool": "input_gate",
                    "version": "1.0",
                    "result": {"pass": False, "reasons": _sorted_reasons(reasons)},
                    "error": None,
                }

    if value_type == "array":
        if len(value) > rules["array"]["max_length"]:
            if add_reason("ARRAY_TOO_LONG", "$", "Array length exceeds max_length."):
                return {
                    "ok": True,
                    "tool": "input_gate",
                    "version": "1.0",
                    "result": {"pass": False, "reasons": _sorted_reasons(reasons)},
                    "error": None,
                }

    if value_type == "object":
        depth = _object_depth(value)
        if depth > rules["object"]["max_depth"]:
            if add_reason("OBJECT_TOO_DEEP", "$", "Object depth exceeds max_depth."):
                return {
                    "ok": True,
                    "tool": "input_gate",
                    "version": "1.0",
                    "result": {"pass": False, "reasons": _sorted_reasons(reasons)},
                    "error": None,
                }
        max_keys = _max_object_keys(value)
        if max_keys > rules["object"]["max_keys"]:
            if add_reason("OBJECT_TOO_MANY_KEYS", "$", "Object key count exceeds max_keys."):
                return {
                    "ok": True,
                    "tool": "input_gate",
                    "version": "1.0",
                    "result": {"pass": False, "reasons": _sorted_reasons(reasons)},
                    "error": None,
                }

    if reasons:
        return {
            "ok": True,
            "tool": "input_gate",
            "version": "1.0",
            "result": {"pass": False, "reasons": _sorted_reasons(reasons)},
            "error": None,
        }

    return {
        "ok": True,
        "tool": "input_gate",
        "version": "1.0",
        "result": {"pass": True, "reasons": []},
        "error": None,
    }


CONTRACT = {
    "name": "input_gate",
    "version": "1.0.0",
    "path": "/tools/input_gate",
    "description": "Pre-flight input checks for type, size, and structural limits.",
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
                "input": {},
                "rules": {"type": "object"},
                "mode": {"type": "string", "enum": ["strict", "permissive"]},
            },
            "required": ["input"],
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
                        "pass": {"type": "boolean"},
                        "reasons": {"type": "array", "items": {"type": "object"}},
                    },
                    "required": ["pass", "reasons"],
                },
                "error": {"type": ["object", "null"]},
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
            {"code": "TYPE_NOT_ALLOWED", "when": "input type is not allowed"},
            {"code": "JSON_TOO_LARGE", "when": "json exceeds max_size"},
            {"code": "STRING_TOO_SHORT", "when": "string below min_length"},
            {"code": "STRING_TOO_LONG", "when": "string exceeds max_length"},
            {"code": "ARRAY_TOO_LONG", "when": "array exceeds max_length"},
            {"code": "OBJECT_TOO_DEEP", "when": "object exceeds max_depth"},
            {"code": "OBJECT_TOO_MANY_KEYS", "when": "object exceeds max_keys"},
            {"code": "RULES_INVALID", "when": "rules are invalid"},
            {"code": "MODE_INVALID", "when": "mode is invalid"},
            {"code": "INPUT_INVALID", "when": "request body invalid"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {"input": "ok"},
            "output": {
                "ok": True,
                "tool": "input_gate",
                "version": "1.0",
                "result": {"pass": True, "reasons": []},
                "error": None,
            },
        }
    ],
}
