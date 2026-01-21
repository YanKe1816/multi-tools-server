from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

router = APIRouter()

MAX_DATA_LENGTH = 20000


class Input(BaseModel):
    schema: dict[str, Any]
    data: Any

    class Config:
        extra = "forbid"


def _fingerprint(tool: str, stage: str, error_class: str, code: str, http_status: int) -> str:
    raw = f"{tool}|{stage}|{error_class}|{code}|{http_status}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _structured_error(code: str, message: str, http_status: int = 400, path: str = "") -> dict[str, Any]:
    error_class = "SCHEMA_UNSUPPORTED" if code == "SCHEMA_UNSUPPORTED" else "INPUT_INVALID"
    return {
        "class": error_class,
        "code": code,
        "message": message,
        "retryable": False,
        "severity": "low",
        "where": {"tool": "schema_validate", "stage": "validate", "path": path},
        "http_status": http_status,
        "fingerprint": _fingerprint("schema_validate", "validate", error_class, code, http_status),
    }


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


def _validate(schema: dict[str, Any], data: Any, path: str, issues: list[dict[str, str]]) -> None:
    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(data, dict):
            issues.append({"path": path, "code": "TYPE_MISMATCH", "message": "Expected object."})
            return
        required = schema.get("required", [])
        for key in sorted(required):
            if key not in data:
                issues.append({"path": f"{path}.{key}", "code": "REQUIRED_MISSING", "message": "Required field missing."})
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            allowed_keys = set(properties.keys())
            for key in sorted(data.keys()):
                if key not in allowed_keys:
                    issues.append({"path": f"{path}.{key}", "code": "ADDITIONAL_PROPERTY", "message": "Additional property not allowed."})
            for key in sorted(properties.keys()):
                child_schema = properties.get(key)
                if key in data and isinstance(child_schema, dict):
                    _validate(child_schema, data[key], f"{path}.{key}", issues)
    elif schema_type == "string":
        if not isinstance(data, str):
            issues.append({"path": path, "code": "TYPE_MISMATCH", "message": "Expected string."})
            return
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if isinstance(min_length, int) and len(data) < min_length:
            issues.append({"path": path, "code": "MIN_LENGTH", "message": f"Minimum length {min_length}."})
        if isinstance(max_length, int) and len(data) > max_length:
            issues.append({"path": path, "code": "MAX_LENGTH", "message": f"Maximum length {max_length}."})
        allowed = schema.get("enum")
        if isinstance(allowed, list) and data not in allowed:
            issues.append({"path": path, "code": "ENUM_MISMATCH", "message": "Value not in enum."})
    elif schema_type == "number":
        if not isinstance(data, (int, float)) or isinstance(data, bool):
            issues.append({"path": path, "code": "TYPE_MISMATCH", "message": "Expected number."})
    elif schema_type == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            issues.append({"path": path, "code": "TYPE_MISMATCH", "message": "Expected integer."})
    elif schema_type == "boolean":
        if not isinstance(data, bool):
            issues.append({"path": path, "code": "TYPE_MISMATCH", "message": "Expected boolean."})
    elif schema_type == "null":
        if data is not None:
            issues.append({"path": path, "code": "TYPE_MISMATCH", "message": "Expected null."})
    elif schema_type == "array":
        if not isinstance(data, list):
            issues.append({"path": path, "code": "TYPE_MISMATCH", "message": "Expected array."})
            return
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(data):
                _validate(item_schema, item, f"{path}[{index}]", issues)
    else:
        issues.append({"path": path, "code": "SCHEMA_INVALID", "message": "Invalid schema type."})


def _sorted_issues(issues: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(issues, key=lambda item: (item["path"], item["code"], item["message"]))


@router.post("/tools/schema_validate")
def schema_validate(payload: dict[str, Any]):
    try:
        data = Input.model_validate(payload)
    except ValidationError:
        error = _structured_error("INPUT_INVALID", "Input must match the schema_validate schema.")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "schema_validate", "version": "1.0", "result": None, "error": error})

    if _schema_size(data.data) > MAX_DATA_LENGTH:
        error = _structured_error("DATA_TOO_LARGE", "Input data is too large.")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "schema_validate", "version": "1.0", "result": None, "error": error})

    unsupported_key = _unsupported_schema(data.schema)
    if unsupported_key:
        error = _structured_error("SCHEMA_UNSUPPORTED", f"Unsupported schema keyword: {unsupported_key}.")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "schema_validate", "version": "1.0", "result": None, "error": error})

    if not isinstance(data.schema, dict):
        error = _structured_error("SCHEMA_INVALID", "Schema must be an object.")
        return JSONResponse(status_code=400, content={"ok": False, "tool": "schema_validate", "version": "1.0", "result": None, "error": error})

    issues: list[dict[str, str]] = []
    _validate(data.schema, data.data, "$", issues)
    ordered_issues = _sorted_issues(issues)

    return {
        "ok": True,
        "tool": "schema_validate",
        "version": "1.0",
        "result": {
            "ok": len(ordered_issues) == 0,
            "issues": ordered_issues,
            "summary": {"issue_count": len(ordered_issues)},
        },
        "error": None,
    }


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
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "version": {"type": "string"},
                "result": {
                    "type": ["object", "null"],
                    "properties": {
                        "ok": {"type": "boolean"},
                        "issues": {"type": "array", "items": {"type": "object"}},
                        "summary": {"type": "object"},
                    },
                    "required": ["ok", "issues", "summary"],
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
            {"code": "INPUT_INVALID", "when": "request body invalid"},
            {"code": "DATA_TOO_LARGE", "when": "input data exceeds max length"},
            {"code": "SCHEMA_UNSUPPORTED", "when": "schema keyword is unsupported"},
            {"code": "SCHEMA_INVALID", "when": "schema type invalid"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {"schema": {"type": "string"}, "data": "ok"},
            "output": {
                "ok": True,
                "tool": "schema_validate",
                "version": "1.0",
                "result": {"ok": True, "issues": [], "summary": {"issue_count": 0}},
                "error": None,
            },
        }
    ],
}
