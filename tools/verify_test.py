from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Input(BaseModel):
    text: str


@router.post("/tools/verify_test")
def verify_test(data: Input):
    return {
        "ok": True,
        "echo": data.text,
        "length": len(data.text),
    }


CONTRACT = {
    "name": "verify_test",
    "version": "1.0.0",
    "path": "/tools/verify_test",
    "description": "Echo input text and return its length for stability verification.",
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
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    "outputs": {
        "content_type": "application/json",
        "json_schema": {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "echo": {"type": "string"},
                "length": {"type": "integer"},
            },
            "required": ["ok", "echo", "length"],
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
        "codes": [],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {"text": "hello"},
            "output": {"ok": True, "echo": "hello", "length": 5},
        }
    ],
}
