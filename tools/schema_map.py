from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError

router = APIRouter()

TOOL_NAME = "schema_map"
TOOL_VERSION = "1.0"


class Mapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rename: dict[str, str] = Field(default_factory=dict)
    drop: list[str] = Field(default_factory=list)
    defaults: dict[str, Any] = Field(default_factory=dict)
    require: list[str] = Field(default_factory=list)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: dict[str, Any]
    mapping: Mapping
    mode: StrictStr = "strict"


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


def _envelope_ok(result: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": result, "error": None}


def _envelope_fail(http_status: int, error: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={"ok": False, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": None, "error": error},
    )


def _is_valid_path(path: str) -> bool:
    if not path or path.startswith(".") or path.endswith("."):
        return False
    parts = path.split(".")
    return all(part.isidentifier() for part in parts)


def _get_path(data: dict[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return False, None
        current = current[key]
    return True, current


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
    current: Any = data
    parts = path.split(".")
    for key in parts[:-1]:
        current = current.setdefault(key, {})
    current[parts[-1]] = value


def _delete_path(data: dict[str, Any], path: str) -> bool:
    current: Any = data
    parts = path.split(".")
    for key in parts[:-1]:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current[key]
    if isinstance(current, dict) and parts[-1] in current:
        del current[parts[-1]]
        return True
    return False


def _validate_paths(mapping: Mapping) -> str | None:
    for source, target in mapping.rename.items():
        if not _is_valid_path(source) or not _is_valid_path(target):
            return source if not _is_valid_path(source) else target
    for path in mapping.drop:
        if not _is_valid_path(path):
            return path
    for path in mapping.defaults.keys():
        if not _is_valid_path(path):
            return path
    for path in mapping.require:
        if not _is_valid_path(path):
            return path
    return None


def _sorted_errors(errors: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(errors, key=lambda item: (item["path"], item["code"], item["message"]))


@router.post("/tools/schema_map")
def schema_map(payload: dict[str, Any]):
    try:
        data = Input.model_validate(payload)
    except ValidationError:
        error = _structured_error("INPUT_INVALID", "Input must match the schema_map schema.", path="")
        return _envelope_fail(400, error)

    if data.mode not in {"strict", "permissive"}:
        error = _structured_error("MODE_INVALID", "Mode must be strict or permissive.", path="mode")
        return _envelope_fail(400, error)

    invalid_path = _validate_paths(data.mapping)
    if invalid_path:
        error = _structured_error("MAPPING_INVALID", f"Invalid path: {invalid_path}.", path=invalid_path)
        return _envelope_fail(400, error)

    output = deepcopy(data.data)
    errors: list[dict[str, str]] = []
    applied: list[str] = []

    # rename (stable order)
    for source, target in sorted(data.mapping.rename.items(), key=lambda item: (item[0], item[1])):
        found, value = _get_path(output, source)
        if not found:
            errors.append({"path": source, "code": "SOURCE_PATH_MISSING", "message": "Rename source path is missing."})
        else:
            _set_path(output, target, value)
            _delete_path(output, source)
            applied.append(f"rename:{source}->{target}")

    # defaults (stable order by target path)
    for target in sorted(data.mapping.defaults.keys()):
        found, _ = _get_path(output, target)
        if not found:
            _set_path(output, target, data.mapping.defaults[target])
            applied.append(f"defaults:{target}")

    # drop (stable order)
    for path in sorted(data.mapping.drop):
        if _delete_path(output, path):
            applied.append(f"drop:{path}")

    # require (stable order)
    for path in sorted(data.mapping.require):
        found, _ = _get_path(output, path)
        if not found:
            errors.append({"path": path, "code": "REQUIRED_MISSING", "message": "Required path is missing."})

    ordered_errors = _sorted_errors(errors)
    strict = data.mode == "strict"
    result_ok = (not ordered_errors) if strict else True

    result: dict[str, Any] = {
        "ok": result_ok,
        "data": output if result_ok else None,
        "meta": {"applied": applied} if result_ok else None,
        "errors": ordered_errors,
    }

    return _envelope_ok(result)


CONTRACT: Dict[str, Any] = {
    "name": "schema_map",
    "version": "1.0.0",
    "path": "/tools/schema_map",
    "description": "Apply deterministic rename/default/drop/require mapping rules to objects.",
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
                "data": {"type": "object"},
                "mapping": {"type": "object"},
                "mode": {"type": "string", "enum": ["strict", "permissive"]},
            },
            "required": ["data", "mapping"],
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
                        "data": {"type": ["object", "null"]},
                        "meta": {
                            "type": ["object", "null"],
                            "properties": {"applied": {"type": "array", "items": {"type": "string"}}},
                            "required": ["applied"],
                            "additionalProperties": False,
                        },
                        "errors": {"type": "array", "items": {"type": "object"}},
                    },
                    "required": ["ok", "data", "meta", "errors"],
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
            {"code": "SOURCE_PATH_MISSING", "when": "rename source missing"},
            {"code": "REQUIRED_MISSING", "when": "required path missing"},
            {"code": "MAPPING_INVALID", "when": "invalid mapping path"},
            {"code": "MODE_INVALID", "when": "mode is invalid"},
            {"code": "INPUT_INVALID", "when": "invalid input"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {"data": {"a": 1}, "mapping": {"rename": {"a": "b"}}},
            "output": {
                "ok": True,
                "tool": "schema_map",
                "version": "1.0",
                "result": {
                    "ok": True,
                    "data": {"b": 1},
                    "meta": {"applied": ["rename:a->b"]},
                    "errors": [],
                },
                "error": None,
            },
        }
    ],
}
