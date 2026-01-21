from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/tools/enum_registry")


class EnumSet(BaseModel):
    name: Any
    version: Any
    items: Any


class Query(BaseModel):
    values: Any
    mode: Any = "strict"


class Policy(BaseModel):
    case_fold: Any = True
    trim: Any = True
    max_values: Any = 100


class Payload(BaseModel):
    enum_set: EnumSet
    query: Query
    policy: Policy = Field(default_factory=Policy)


def _normalize(value: str, trim: bool, case_fold: bool) -> str:
    result = value
    if trim:
        result = result.strip()
    if case_fold:
        result = result.lower()
    return result


def _error(code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": {"code": code, "message": message}})


@router.post("/")
def enum_registry(payload: Payload):
    policy = payload.policy
    if not isinstance(policy.case_fold, bool) or not isinstance(policy.trim, bool):
        return _error("POLICY_INVALID", "policy.case_fold and policy.trim must be boolean.")
    if not isinstance(policy.max_values, int) or policy.max_values <= 0:
        return _error("POLICY_INVALID", "policy.max_values must be a positive integer.")

    enum_set = payload.enum_set
    if not isinstance(enum_set.name, str) or not isinstance(enum_set.version, str):
        return _error("ENUM_INVALID", "enum_set.name and enum_set.version must be strings.")
    if not isinstance(enum_set.items, list):
        return _error("ENUM_INVALID", "enum_set.items must be a list.")
    if len(enum_set.items) == 0:
        return _error("ENUM_EMPTY", "enum_set.items is empty.")

    query = payload.query
    if not isinstance(query.values, list):
        return _error("ENUM_INVALID", "query.values must be a list of strings.")
    if query.mode not in {"strict", "permissive"}:
        return _error("ENUM_INVALID", "query.mode must be strict or permissive.")
    if query.mode == "strict" and len(query.values) == 0:
        return _error("ENUM_INVALID", "query.values empty")
    if len(query.values) > policy.max_values:
        return _error("TOO_MANY_VALUES", "query.values exceeds policy.max_values.")
    if not all(isinstance(value, str) for value in query.values):
        return _error("ENUM_INVALID", "query.values must be a list of strings.")

    key_map: dict[str, set[str]] = {}
    alias_map: dict[str, set[str]] = {}

    for item in enum_set.items:
        if not isinstance(item, dict):
            return _error("ENUM_INVALID", "enum_set.items entries must be objects.")
        key = item.get("key")
        aliases = item.get("aliases", [])
        meta = item.get("meta", {})
        if not isinstance(key, str):
            return _error("ENUM_INVALID", "enum_set.items.key must be a string.")
        if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
            return _error("ENUM_INVALID", "enum_set.items.aliases must be a list of strings.")
        if not isinstance(meta, dict):
            return _error("ENUM_INVALID", "enum_set.items.meta must be an object.")

        normalized_key = _normalize(key, policy.trim, policy.case_fold)
        key_map.setdefault(normalized_key, set()).add(key)
        for alias in aliases:
            normalized_alias = _normalize(alias, policy.trim, policy.case_fold)
            alias_map.setdefault(normalized_alias, set()).add(key)

    matched: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    duplicates: list[dict[str, str]] = []

    for value in query.values:
        normalized_value = _normalize(value, policy.trim, policy.case_fold)
        key_hits = key_map.get(normalized_value, set())
        if key_hits:
            if len(key_hits) > 1:
                duplicates.append({"input": value, "code": "AMBIGUOUS_ALIAS"})
            else:
                matched.append({"input": value, "key": sorted(key_hits)[0]})
            continue

        alias_hits = alias_map.get(normalized_value, set())
        if alias_hits:
            if len(alias_hits) > 1:
                duplicates.append({"input": value, "code": "AMBIGUOUS_ALIAS"})
            else:
                matched.append({"input": value, "key": sorted(alias_hits)[0]})
        else:
            missing.append({"input": value, "code": "NOT_IN_ENUM"})

    matched.sort(key=lambda item: item["input"])
    missing.sort(key=lambda item: item["input"])
    duplicates.sort(key=lambda item: item["input"])

    return {
        "ok": True,
        "result": {
            "name": enum_set.name,
            "version": enum_set.version,
            "matched": matched,
            "missing": missing,
            "duplicates": duplicates,
        },
    }


# Self-test hints (local):
# curl -X POST http://localhost:8000/tools/enum_registry/ \
#   -H "Content-Type: application/json" \
#   -d '{"enum_set":{"name":"status","version":"1","items":[{"key":"OPEN","aliases":["open"],"meta":{"deprecated":false}}]},"query":{"values":["open"],"mode":"strict"},"policy":{"case_fold":true,"trim":true,"max_values":100}}'
#
# curl -X POST http://localhost:8000/tools/enum_registry/ \
#   -H "Content-Type: application/json" \
#   -d '{"enum_set":{"name":"status","version":"1","items":[]},"query":{"values":["open"],"mode":"strict"},"policy":{"case_fold":true,"trim":true,"max_values":100}}'
#
# curl -X POST http://localhost:8000/tools/enum_registry/ \
#   -H "Content-Type: application/json" \
#   -d '{"enum_set":{"name":"status","version":"1","items":[{"key":"OPEN","aliases":["o"],"meta":{}} ,{"key":"OPEN2","aliases":["o"],"meta":{}}]},"query":{"values":["o"],"mode":"strict"},"policy":{"case_fold":true,"trim":true,"max_values":100}}'


CONTRACT = {
    "name": "enum_registry",
    "version": "1.0.0",
    "path": "/tools/enum_registry",
    "description": "Normalize and validate enum sets for matching query values.",
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
                "enum_set": {"type": "object"},
                "query": {"type": "object"},
                "policy": {"type": "object"},
            },
            "required": ["enum_set", "query", "policy"],
            "additionalProperties": False,
        },
    },
    "outputs": {
        "content_type": "application/json",
        "json_schema": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}, "result": {"type": "object"}},
            "required": ["ok", "result"],
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
            {"code": "ENUM_EMPTY", "when": "enum_set.items is empty"},
            {"code": "ENUM_INVALID", "when": "enum_set/query structure invalid"},
            {"code": "TOO_MANY_VALUES", "when": "query.values exceeds max_values"},
            {"code": "POLICY_INVALID", "when": "policy invalid"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {
                "enum_set": {"name": "status", "version": "1", "items": [{"key": "OPEN", "aliases": ["open"], "meta": {}}]},
                "query": {"values": ["open"], "mode": "strict"},
                "policy": {"case_fold": True, "trim": True, "max_values": 100},
            },
            "output": {
                "ok": True,
                "result": {"name": "status", "version": "1", "matched": [{"input": "open", "key": "OPEN"}], "missing": [], "duplicates": []},
            },
        }
    ],
}
