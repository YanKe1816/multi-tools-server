from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

MAX_DATA_LENGTH = 20000


class Input(BaseModel):
    schema: dict[str, Any]
    data: Any


def _schema_size(data: Any) -> int:
    return len(json.dumps(data, ensure_ascii=False))


def _unsupported_schema(schema: Any) -> str | None:
    if isinstance(schema, dict):
        allowed = {
            "type",
            "properties",
            "required",
            "minLength",
            "maxLength",
            "enum",
            "items",
        }
        for key, value in schema.items():
            if key not in allowed:
                return key
            if key == "properties" and isinstance(value, dict):
                for child in value.values():
                    unsupported = _unsupported_schema(child)
                    if unsupported:
                        return unsupported
            if key == "items":
                unsupported = _unsupported_schema(value)
                if unsupported:
                    return unsupported
        return None
    if isinstance(schema, list):
        for item in schema:
            unsupported = _unsupported_schema(item)
            if unsupported:
                return unsupported
    return None


def _validate(schema: dict[str, Any], data: Any, path: str, errors: list[str]) -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(data, dict):
            errors.append(f"{path}: expected object")
            return
        required = schema.get("required", [])
        for key in required:
            if key not in data:
                errors.append(f"{path}.{key}: required")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in data and isinstance(child_schema, dict):
                    _validate(child_schema, data[key], f"{path}.{key}", errors)
    elif schema_type == "string":
        if not isinstance(data, str):
            errors.append(f"{path}: expected string")
            return
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if isinstance(min_length, int) and len(data) < min_length:
            errors.append(f"{path}: minLength {min_length}")
        if isinstance(max_length, int) and len(data) > max_length:
            errors.append(f"{path}: maxLength {max_length}")
        allowed = schema.get("enum")
        if isinstance(allowed, list) and data not in allowed:
            errors.append(f"{path}: enum")
    elif schema_type == "number":
        if not isinstance(data, (int, float)) or isinstance(data, bool):
            errors.append(f"{path}: expected number")
    elif schema_type == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            errors.append(f"{path}: expected integer")
    elif schema_type == "boolean":
        if not isinstance(data, bool):
            errors.append(f"{path}: expected boolean")
    elif schema_type == "null":
        if data is not None:
            errors.append(f"{path}: expected null")
    elif schema_type == "array":
        if not isinstance(data, list):
            errors.append(f"{path}: expected array")
            return
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(data):
                _validate(item_schema, item, f"{path}[{index}]", errors)
    else:
        errors.append(f"{path}: invalid schema type")


@router.post("/tools/schema_validate")
def schema_validate(data: Input):
    if _schema_size(data.data) > MAX_DATA_LENGTH:
        return JSONResponse(
            status_code=400,
            content={
                "error": {"code": "DATA_TOO_LARGE", "message": "Input data is too large."}
            },
        )

    unsupported_key = _unsupported_schema(data.schema)
    if unsupported_key:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "SCHEMA_UNSUPPORTED",
                    "message": f"Unsupported schema keyword: {unsupported_key}.",
                }
            },
        )

    errors: list[str] = []
    if not isinstance(data.schema, dict):
        errors.append("$: schema must be an object")
    else:
        _validate(data.schema, data.data, "$", errors)

    return {"valid": len(errors) == 0, "errors": errors}


CONTRACT = {
    "name": "schema_validate",
    "version": "1.0.0",
    "path": "/tools/schema_validate",
    "description": "Validate data against a limited JSON Schema subset.",
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
                "schema": {"type": "object"},
                "data": {},
            },
            "required": ["schema", "data"],
            "additionalProperties": False,
        },
    },
    "outputs": {
        "content_type": "application/json",
        "json_schema": {
            "type": "object",
            "properties": {
                "valid": {"type": "boolean"},
                "errors": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["valid", "errors"],
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
            {"code": "DATA_TOO_LARGE", "when": "input data exceeds max length"},
            {"code": "SCHEMA_UNSUPPORTED", "when": "schema keyword is unsupported"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {"schema": {"type": "string"}, "data": "ok"},
            "output": {"valid": True, "errors": []},
        }
    ],
}
