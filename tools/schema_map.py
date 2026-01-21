from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


class Mapping(BaseModel):
    rename: dict[str, str] = {}
    drop: list[str] = []
    defaults: dict[str, Any] = {}
    require: list[str] = []


class Input(BaseModel):
    data: dict[str, Any]
    mapping: Mapping
    mode: str = "strict"


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


@router.post("/tools/schema_map")
def schema_map(payload: Input):
    if payload.mode not in {"strict", "permissive"}:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INPUT_INVALID", "message": "Mode must be strict or permissive."}},
        )

    invalid_path = _validate_paths(payload.mapping)
    if invalid_path:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "MAPPING_INVALID",
                    "message": f"Invalid path: {invalid_path}.",
                }
            },
        )

    data = deepcopy(payload.data)
    errors: list[dict[str, str]] = []
    applied: list[str] = []

    for source, target in payload.mapping.rename.items():
        found, value = _get_path(data, source)
        if not found:
            errors.append(
                {
                    "path": source,
                    "code": "SOURCE_PATH_MISSING",
                    "message": "Rename source path is missing.",
                }
            )
        else:
            _set_path(data, target, value)
            _delete_path(data, source)
            applied.append(f"rename:{source}->{target}")

    for target, value in payload.mapping.defaults.items():
        found, _ = _get_path(data, target)
        if not found:
            _set_path(data, target, value)
            applied.append(f"defaults:{target}")

    for path in payload.mapping.drop:
        if _delete_path(data, path):
            applied.append(f"drop:{path}")

    for path in payload.mapping.require:
        found, _ = _get_path(data, path)
        if not found:
            errors.append(
                {
                    "path": path,
                    "code": "REQUIRED_MISSING",
                    "message": "Required path is missing.",
                }
            )

    if errors:
        return {"ok": False, "errors": errors}

    return {"ok": True, "data": data, "meta": {"applied": applied}}


CONTRACT = {
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
                "data": {"type": "object"},
                "meta": {"type": "object"},
                "errors": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["ok"],
            "additionalProperties": True,
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
            {"code": "INPUT_INVALID", "when": "invalid input"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {"data": {"a": 1}, "mapping": {"rename": {"a": "b"}}},
            "output": {"ok": True, "data": {"b": 1}, "meta": {"applied": ["rename:a->b"]}},
        }
    ],
}
