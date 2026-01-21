from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

SUPPORTED_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}
ALLOWED_KEYS = {"type", "properties", "required", "items", "enum"}
FORBIDDEN_KEYS = {"$ref", "anyOf", "oneOf", "allOf", "not", "if", "then", "else"}


class Options(BaseModel):
    compare_required: bool = True
    compare_type: bool = True
    compare_enum: bool = True
    ignore_order: bool = True


class Input(BaseModel):
    old_schema: dict[str, Any]
    new_schema: dict[str, Any]
    options: Options | None = None


def _normalize_enum(enum_values: list[Any], ignore_order: bool) -> list[Any]:
    if ignore_order:
        try:
            return sorted(set(enum_values))
        except TypeError:
            return sorted(enum_values, key=lambda item: json.dumps(item, sort_keys=True))
    return list(enum_values)


def _find_unsupported(schema: Any) -> str | None:
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in FORBIDDEN_KEYS:
                return key
            if key not in ALLOWED_KEYS:
                return key
            if key == "type":
                if not isinstance(value, str) or value not in SUPPORTED_TYPES:
                    return key
            if key == "properties":
                if not isinstance(value, dict):
                    return key
                for child in value.values():
                    unsupported = _find_unsupported(child)
                    if unsupported:
                        return unsupported
            if key == "required":
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    return key
            if key == "items":
                if not isinstance(value, dict):
                    return key
                unsupported = _find_unsupported(value)
                if unsupported:
                    return unsupported
            if key == "enum":
                if not isinstance(value, list):
                    return key
        return None
    if isinstance(schema, list):
        for item in schema:
            unsupported = _find_unsupported(item)
            if unsupported:
                return unsupported
    return None


def _walk_schema(
    schema: dict[str, Any],
    path: str,
    required_flag: bool | None,
    mapping: dict[str, dict[str, Any]],
    ignore_order: bool,
) -> None:
    node_type = schema.get("type", "unknown")
    enum_values = schema.get("enum")
    enum_list = None
    if isinstance(enum_values, list):
        enum_list = _normalize_enum(enum_values, ignore_order)

    if path:
        mapping[path] = {
            "type": node_type if isinstance(node_type, str) else "unknown",
            "required": required_flag,
            "enum": enum_list,
        }

    if node_type == "object":
        properties = schema.get("properties", {})
        required_list = schema.get("required", [])
        required_set = set(required_list) if isinstance(required_list, list) else set()
        if isinstance(properties, dict):
            for key, child in properties.items():
                child_path = f"{path}.{key}" if path else key
                if isinstance(child, dict):
                    _walk_schema(child, child_path, key in required_set, mapping, ignore_order)
    if node_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            child_path = f"{path}[]" if path else "[]"
            _walk_schema(items, child_path, None, mapping, ignore_order)


def _detail(parts: list[str]) -> str:
    return "; ".join(parts)


@router.post("/tools/schema_diff")
def schema_diff(payload: Input):
    options = payload.options or Options()

    if not isinstance(payload.old_schema, dict) or not isinstance(payload.new_schema, dict):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_INPUT", "message": "Schemas must be objects."}},
        )

    if not isinstance(options.compare_required, bool) or not isinstance(options.compare_type, bool):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "OPTIONS_INVALID", "message": "Options must be booleans."}},
        )
    if not isinstance(options.compare_enum, bool) or not isinstance(options.ignore_order, bool):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "OPTIONS_INVALID", "message": "Options must be booleans."}},
        )

    unsupported_old = _find_unsupported(payload.old_schema)
    unsupported_new = _find_unsupported(payload.new_schema)
    unsupported_key = unsupported_old or unsupported_new
    if unsupported_key:
        message = "ref is not supported" if unsupported_key == "$ref" else "unsupported schema keyword"
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "SCHEMA_UNSUPPORTED", "message": message}},
        )

    old_map: dict[str, dict[str, Any]] = {}
    new_map: dict[str, dict[str, Any]] = {}

    _walk_schema(payload.old_schema, "", None, old_map, options.ignore_order)
    _walk_schema(payload.new_schema, "", None, new_map, options.ignore_order)

    added = []
    removed = []
    changed = []

    for path in sorted(new_map.keys() - old_map.keys()):
        node = new_map[path]
        added.append({"path": path, "type": node.get("type", "unknown")})

    for path in sorted(old_map.keys() - new_map.keys()):
        node = old_map[path]
        removed.append({"path": path, "type": node.get("type", "unknown")})

    for path in sorted(old_map.keys() & new_map.keys()):
        old_node = old_map[path]
        new_node = new_map[path]
        parts = []

        if options.compare_type and old_node.get("type") != new_node.get("type"):
            parts.append(f"type:{old_node.get('type')} -> {new_node.get('type')}")
        if options.compare_required and old_node.get("required") != new_node.get("required"):
            parts.append(f"required:{old_node.get('required')} -> {new_node.get('required')}")
        if options.compare_enum and old_node.get("enum") != new_node.get("enum"):
            parts.append(f"enum:{old_node.get('enum')} -> {new_node.get('enum')}")

        if parts:
            detail = _detail(parts)
            changed.append(
                {
                    "path": path,
                    "from": {"type": old_node.get("type", "unknown"), "detail": detail},
                    "to": {"type": new_node.get("type", "unknown"), "detail": detail},
                }
            )

    return {"ok": True, "diff": {"added": added, "removed": removed, "changed": changed}}


# Self-test hints (local):
# curl -X POST http://localhost:8000/tools/schema_diff \
#   -H "Content-Type: application/json" \
#   -d '{"old_schema":{"type":"object","properties":{"name":{"type":"string"}}},"new_schema":{"type":"object","properties":{"name":{"type":"string"},"age":{"type":"integer"}}}}'
#
# curl -X POST http://localhost:8000/tools/schema_diff \
#   -H "Content-Type: application/json" \
#   -d '{"old_schema":{"$ref":"#/defs/x"},"new_schema":{"type":"object"}}'
#
# curl -X POST http://localhost:8000/tools/schema_diff \
#   -H "Content-Type: application/json" \
#   -d '{"old_schema":{"type":"object","properties":{"tags":{"type":"array","items":{"type":"string"}}}},"new_schema":{"type":"object","properties":{"tags":{"type":"array","items":{"type":"integer"}}}}}'


CONTRACT = {
    "name": "schema_diff",
    "version": "1.0.0",
    "path": "/tools/schema_diff",
    "description": "Diff two JSON Schemas and return added/removed/changed paths.",
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
                "old_schema": {"type": "object"},
                "new_schema": {"type": "object"},
                "options": {"type": "object"},
            },
            "required": ["old_schema", "new_schema"],
            "additionalProperties": False,
        },
    },
    "outputs": {
        "content_type": "application/json",
        "json_schema": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}, "diff": {"type": "object"}},
            "required": ["ok", "diff"],
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
            {"code": "INVALID_INPUT", "when": "schemas are not objects"},
            {"code": "OPTIONS_INVALID", "when": "options are not boolean"},
            {"code": "SCHEMA_UNSUPPORTED", "when": "schema uses unsupported keywords"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {
                "old_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
                "new_schema": {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}},
            },
            "output": {"ok": True, "diff": {"added": [{"path": "age", "type": "integer"}], "removed": [], "changed": []}},
        }
    ],
}
