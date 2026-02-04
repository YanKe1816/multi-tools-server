from fastapi import APIRouter
from pydantic import BaseModel, Field, StrictInt, StrictStr, ValidationError
import hashlib

from tools._shared.errors import make_error

router = APIRouter()


class Input(BaseModel):
    text: StrictStr = ""
    max_len: StrictInt = Field(default=2000, ge=0)

    class Config:
        extra = "forbid"


@router.post("/tools/verify_test")
def verify_test(payload: dict):
    try:
        data = Input.model_validate(payload)
    except ValidationError:
        return make_error("INPUT_INVALID", "Input must match the verify_test schema.")

    if len(data.text) > data.max_len:
        return make_error("INPUT_TOO_LONG", "Input text exceeds max_len.")

    digest = hashlib.sha256(data.text.encode("utf-8")).hexdigest()
    return {
        "ok": True,
        "tool": "verify_test",
        "version": "1.0.0",
        "result": {"text": data.text, "length": len(data.text), "sha256": digest},
    }


CONTRACT = {
    "name": "verify_test",
    "version": "1.0.0",
    "path": "/tools/verify_test",
    "description": "Probe tool for stability verification (deterministic echo + length + sha256).",
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
            "properties": {"text": {"type": "string"}, "max_len": {"type": "integer"}},
            "required": [],
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
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "length": {"type": "integer"},
                        "sha256": {"type": "string"},
                    },
                    "required": ["text", "length", "sha256"],
                    "additionalProperties": False,
                },
            },
            "required": ["ok", "tool", "version", "result"],
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
            {"code": "INPUT_TOO_LONG", "when": "text exceeds max_len"},
        ],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {"text": "hello"},
            "output": {
                "ok": True,
                "tool": "verify_test",
                "version": "1.0.0",
                "result": {
                    "text": "hello",
                    "length": 5,
                    "sha256": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
                },
            },
        }
    ],
}
