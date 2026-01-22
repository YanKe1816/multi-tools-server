from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, ValidationError

router = APIRouter()

TOOL_NAME = "schema_diff"
TOOL_VERSION = "1.0"

SUPPORTED_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}
ALLOWED_KEYS = {"type", "properties", "required", "items", "enum"}
FORBIDDEN_KEYS = {"$ref", "anyOf", "oneOf", "allOf", "not", "if", "then", "else"}


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compare_required: StrictBool = True
    compare_type: StrictBool = True
    compare_enum: StrictBool = True
    ignore_order: StrictBool = True


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    old_schema: dict[str, Any]
    new_schema: dict[str, Any]
    options: Optional[Options] = None


def _fingerprint(tool: str, stage: str, error_class: str, code: str, http_status: int) -> str:
    raw = f"{tool}|{stage}|{error_class}|{code}|{http_status}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _structured_error(
    code: str,
    message: str,
    http_status: int = 400,
    path: str = "",
    error_class: str = "INPUT_INVALID",
) -> dict[str, Any]:
    severity = "low" if error_class == "INPUT_INVALID" else "medium"
    return {
        "class": error_class,
        "code": code,
        "message": message,
        "retryable": False,
        "severity": severity,
        "where": {"tool": TOOL_NAME, "stage": "validate", "path": path},
        "http_status": http_status,
        "fingerprint": _fingerprint(TOOL_NAME, "validate", error_class, code, http_status),
    }


def _ok(result: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": result, "error": None}


def _fail(http_status: int, error: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"ok": False, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": None, "error": error},
    )


def _normalize_enum(enum_values: list[Any], ignore_order: bool) -> list[Any]:
    if ignore_order:
        try:
            return sorted(set(enum_values))
        except TypeError:
            return sorted(enum_values, key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
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
def schema_diff(payload: dict[str, Any]):
    try:
        data = Input.model_validate(payload)
    except ValidationError:
        error = _structured_error("INPUT_INVALID", "Input must match the schema_diff schema.", path="")
        return _fail(400, error)

    options = data.options or Options()

    unsupported_old = _find_unsupported(data.old_schema)
    unsupported_new = _find_unsupported(data.new_schema)
    unsupported_key = unsupported_old or unsupported_new
    if unsupported_key:
        message = "ref is not supported" if unsupported_key == "$ref" else "unsupported schema keyword"
        error = _structured_error(
            "SCHEMA_UNSUPPORTED",
            message,
            http_status=400,
            path=unsupported_key,
            error_class="SCHEMA_UNSUPPORTED",
        )
        return _fail(400, error)

    old_map: dict[str, dict[str, Any]] = {}
    new_map: dict[str, dict[str, Any]] = {}

    _walk_schema(data.old_schema, "", None, old_map, options.ignore_order)
    _walk_schema(data.new_schema, "", None, new_map, options.ignore_order)

    added_fields: list[dict[str, Any]] = []
    removed_fields: list[dict[str, Any]] = []
    changed_fields: list[dict[str, Any]] = []

    for path in sorted(new_map.keys() - old_map.keys()):
        node = new_map[path]
        added_fields.append({"path": path, "schema": node})

    for path in sorted(old_map.keys() - new_map.keys()):
        node = old_map[path]
        removed_fields.append({"path": path, "schema": node})

    for path in sorted(old_map.keys() & new_map.keys()):
        old_node = old_map[path]
        new_node = new_map[path]
        parts: list[str] = []

        if options.compare_type and old_node.get("type") != new_node.get("type"):
            parts.append(f"type:{old_node.get('type')} -> {new_node.get('type')}")
        if options.compare_required and old_node.get("required") != new_node.get("required"):
            parts.append(f"required:{old_node.get('required')} -> {new_node.get('required')}")
        if options.compare_enum and old_node.get("enum") != new_node.get("enum"):
            parts.append(f"enum:{old_node.get('enum')} -> {new_node.get('enum')}")

        if parts:
            detail = _detail(parts)
            changed_fields.append(
                {
                    "path": path,
                    "before": {**old_node, "detail": detail},
                    "after": {**new_node, "detail": detail},
                }
            )

    return _ok({"diff": {"added_fields": added_fields, "removed_fields": removed_fields, "changed_fields": changed_fields}})


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


CONTRACT: Dict[str, Any] = {
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
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "version": {"type": "string"},
                "result": {
                    "type": ["object", "null"],
                    "properties": {
                        "diff": {
                            "type": "object",
                            "properties": {
                                "added_fields": {"type": "array", "items": {"type": "object"}},
                                "removed_fields": {"type": "array", "items": {"type": "object"}},
                                "changed_fields": {"type": "array", "items": {"type": "object"}},
                            },
                            "required": ["added_fields", "removed_fields", "changed_fields"],
                            "additionalProperties": False,
                        }
                    },
                    "required": ["diff"],
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
            {"code": "SCHEMA_UNSUPPORTED", "when": "schema uses unsupported keywords"},
            {"code": "INPUT_INVALID", "when": "request body invalid"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {
                "old_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
                "new_schema": {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}},
            },
            "output": {
                "ok": True,
                "tool": "schema_diff",
                "version": "1.0",
                "result": {
                    "diff": {
                        "added_fields": [{"path": "age", "schema": {"type": "integer", "required": False, "enum": None}}],
                        "removed_fields": [],
                        "changed_fields": [],
                    }
                },
                "error": None,
            },
        }
    ],
}
