from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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
    mode: str = "strict"


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


@router.post("/tools/input_gate")
def input_gate(payload: Input):
    if payload.mode not in {"strict", "permissive"}:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "MODE_INVALID", "message": "Mode must be strict or permissive."}},
        )

    rules = _merge_rules(payload.rules)
    if not _rules_valid(rules):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "RULES_INVALID", "message": "Rules are invalid."}},
        )

    errors: list[dict[str, str]] = []
    strict = payload.mode == "strict"

    def add_error(code: str, path: str, message: str) -> bool:
        errors.append({"code": code, "path": path, "message": message})
        return strict

    value = payload.input
    value_type = _type_name(value)
    if value_type == "unknown" or value_type not in rules["allow_types"]:
        if add_error("TYPE_NOT_ALLOWED", "$", "Input type is not allowed."):
            return {"pass": False, "errors": errors}

    if _json_size(value) > rules["max_size"]:
        if add_error("JSON_TOO_LARGE", "$", "JSON size exceeds max_size."):
            return {"pass": False, "errors": errors}

    if value_type == "string":
        length = len(value)
        if length < rules["string"]["min_length"]:
            if add_error("STRING_TOO_SHORT", "$", "String length is below min_length."):
                return {"pass": False, "errors": errors}
        if length > rules["string"]["max_length"]:
            if add_error("STRING_TOO_LONG", "$", "String length exceeds max_length."):
                return {"pass": False, "errors": errors}

    if value_type == "array":
        if len(value) > rules["array"]["max_length"]:
            if add_error("ARRAY_TOO_LONG", "$", "Array length exceeds max_length."):
                return {"pass": False, "errors": errors}

    if value_type == "object":
        depth = _object_depth(value)
        if depth > rules["object"]["max_depth"]:
            if add_error("OBJECT_TOO_DEEP", "$", "Object depth exceeds max_depth."):
                return {"pass": False, "errors": errors}
        max_keys = _max_object_keys(value)
        if max_keys > rules["object"]["max_keys"]:
            if add_error("OBJECT_TOO_MANY_KEYS", "$", "Object key count exceeds max_keys."):
                return {"pass": False, "errors": errors}

    if errors:
        return {"pass": False, "errors": errors}

    return {"pass": True}
