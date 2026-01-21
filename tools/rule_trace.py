from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter()


class Run(BaseModel):
    run_id: str
    ts: str
    actor: str
    tool: str
    tool_version: str
    stage: str


class Summary(BaseModel):
    type: str
    size: int
    hash: str


class RuleHit(BaseModel):
    rule_id: str
    kind: str
    path: str
    code: str
    message: str


class ResultError(BaseModel):
    code: str
    message: str
    class_name: str | None = Field(default=None, alias="class")

    class Config:
        allow_population_by_field_name = True


class Result(BaseModel):
    ok: bool
    output_summary: Summary | None = None
    rules_hit: list[RuleHit] = []
    error: ResultError | None = None


class Input(BaseModel):
    summary: Summary


class Policy(BaseModel):
    max_message_length: int = 200
    hash_alg: str = "sha256"


class Payload(BaseModel):
    run: Run
    input: Input
    result: Result
    policy: Policy


def _truncate(message: str, limit: int) -> str:
    if len(message) <= limit:
        return message
    return f"{message[:limit]}..."


@router.post("/tools/rule_trace")
def rule_trace(payload: Payload):
    if payload.policy.hash_alg != "sha256":
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "POLICY_INVALID",
                    "message": "policy.hash_alg must be sha256.",
                }
            },
        )

    max_length = payload.policy.max_message_length
    rules_hit = []
    for rule in payload.result.rules_hit:
        rules_hit.append(
            {
                "rule_id": rule.rule_id,
                "kind": rule.kind,
                "path": rule.path,
                "code": rule.code,
                "message": _truncate(rule.message, max_length),
            }
        )

    error = payload.result.error
    if error is not None:
        _truncate(error.message, max_length)

    if error is not None:
        status = "error"
    elif payload.result.ok is False and any(item["kind"] == "reject" for item in rules_hit):
        status = "rejected"
    else:
        status = "success"

    output_summary = payload.result.output_summary

    trace = {
        "run_id": payload.run.run_id,
        "ts": payload.run.ts,
        "actor": payload.run.actor,
        "tool": payload.run.tool,
        "tool_version": payload.run.tool_version,
        "stage": payload.run.stage,
        "input": {
            "type": payload.input.summary.type,
            "size": payload.input.summary.size,
            "hash": payload.input.summary.hash,
        },
        "output": {
            "type": output_summary.type if output_summary else "",
            "size": output_summary.size if output_summary else 0,
            "hash": output_summary.hash if output_summary else "",
        },
        "rules_hit": rules_hit,
        "status": status,
    }

    return {"ok": True, "trace": trace}


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
                "run": {"type": "object"},
                "input": {"type": "object"},
                "result": {"type": "object"},
                "policy": {"type": "object"},
            },
            "required": ["run", "input", "result", "policy"],
            "additionalProperties": False,
        },
    },
    "outputs": {
        "content_type": "application/json",
        "json_schema": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}, "trace": {"type": "object"}},
            "required": ["ok", "trace"],
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
        "codes": [{"code": "POLICY_INVALID", "when": "hash_alg is not sha256"}],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {
                "run": {"run_id": "r1", "ts": "t", "actor": "system", "tool": "x", "tool_version": "1", "stage": "s"},
                "input": {"summary": {"type": "string", "size": 1, "hash": "h"}},
                "result": {"ok": True, "output_summary": {"type": "string", "size": 1, "hash": "h"}, "rules_hit": []},
                "policy": {"max_message_length": 200, "hash_alg": "sha256"},
            },
            "output": {"ok": True, "trace": {"status": "success"}},
        }
    ],
}
