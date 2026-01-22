"""
text_normalize

Request JSON schema:
{
  "type": "object",
  "properties": {
    "text": {"type": "string"},
    "ops": {
      "type": "object",
      "properties": {
        "normalize_newlines": {"type": "boolean"},
        "collapse_whitespace": {"type": "boolean"},
        "trim": {"type": "boolean"},
        "to_lower": {"type": "boolean"},
        "to_upper": {"type": "boolean"},
        "remove_control_chars": {"type": "boolean"}
      },
      "additionalProperties": false
    },
    "options": {
      "type": "object",
      "properties": {
        "preserve_tabs": {"type": "boolean"},
        "preserve_newlines": {"type": "boolean"}
      },
      "additionalProperties": false
    }
  },
  "required": ["text"],
  "additionalProperties": false
}

Response JSON schema:
{
  "type": "object",
  "properties": {
    "ok": {"type": "boolean"},
    "tool": {"type": "string"},
    "version": {"type": "string"},
    "result": {
      "type": ["object", "null"],
      "properties": {
        "text": {"type": "string"},
        "meta": {
          "type": "object",
          "properties": {
            "original_length": {"type": "integer"},
            "normalized_length": {"type": "integer"},
            "applied": {"type": "array", "items": {"type": "string"}}
          },
          "required": ["original_length", "normalized_length", "applied"],
          "additionalProperties": false
        }
      },
      "required": ["text", "meta"],
      "additionalProperties": false
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
          "properties": {"tool": {"type": "string"}, "stage": {"type": "string"}, "path": {"type": "string"}},
          "required": ["tool", "stage", "path"],
          "additionalProperties": false
        },
        "http_status": {"type": "integer"},
        "fingerprint": {"type": "string"}
      },
      "required": ["class", "code", "message", "retryable", "severity", "where", "http_status", "fingerprint"],
      "additionalProperties": false
    }
  },
  "required": ["ok", "tool", "version", "result", "error"],
  "additionalProperties": false
}
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError

router = APIRouter()

TOOL_NAME = "text_normalize"
TOOL_VERSION = "1.0"


class Ops(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalize_newlines: StrictBool = False
    collapse_whitespace: StrictBool = False
    trim: StrictBool = False
    to_lower: StrictBool = False
    to_upper: StrictBool = False
    remove_control_chars: StrictBool = False


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preserve_tabs: StrictBool = True
    preserve_newlines: StrictBool = True


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: StrictStr
    ops: Ops = Field(default_factory=Ops)
    options: Options = Field(default_factory=Options)


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


def _collapse_whitespace(text: str, preserve_tabs: bool, preserve_newlines: bool) -> str:
    if preserve_newlines:
        lines = text.split("\n")
        collapsed_lines = []
        for line in lines:
            if preserve_tabs:
                collapsed_lines.append(re.sub(r"[ ]+", " ", line))
            else:
                collapsed_lines.append(re.sub(r"[\t ]+", " ", line))
        return "\n".join(collapsed_lines)

    if preserve_tabs:
        return re.sub(r"[ ]+", " ", text)
    return re.sub(r"[\t ]+", " ", text)


def _remove_control_chars(text: str, preserve_tabs: bool, preserve_newlines: bool) -> str:
    allowed = {"\t", "\n"}
    if not preserve_tabs:
        allowed.discard("\t")
    if not preserve_newlines:
        allowed.discard("\n")
    return "".join(ch for ch in text if ord(ch) >= 32 or ch in allowed)


@router.post("/tools/text_normalize")
def text_normalize(payload: dict[str, Any]):
    try:
        data = Input.model_validate(payload)
    except ValidationError:
        err = _structured_error("INPUT_INVALID", "Input must match the text_normalize schema.")
        return JSONResponse(
            status_code=400,
            content={"ok": False, "tool": TOOL_NAME, "version": TOOL_VERSION, "result": None, "error": err},
        )

    text = data.text
    ops = data.ops
    options = data.options
    applied: list[str] = []

    if ops.normalize_newlines:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if normalized != text:
            applied.append("normalize_newlines")
        text = normalized

    if ops.remove_control_chars:
        normalized = _remove_control_chars(text, options.preserve_tabs, options.preserve_newlines)
        if normalized != text:
            applied.append("remove_control_chars")
        text = normalized

    if ops.collapse_whitespace:
        normalized = _collapse_whitespace(text, options.preserve_tabs, options.preserve_newlines)
        if normalized != text:
            applied.append("collapse_whitespace")
        text = normalized

    if ops.trim:
        normalized = text.strip()
        if normalized != text:
            applied.append("trim")
        text = normalized

    if ops.to_lower:
        normalized = text.lower()
        if normalized != text:
            applied.append("to_lower")
        text = normalized

    if ops.to_upper:
        normalized = text.upper()
        if normalized != text:
            applied.append("to_upper")
        text = normalized

    return {
        "ok": True,
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "result": {
            "text": text,
            "meta": {
                "original_length": len(data.text),
                "normalized_length": len(text),
                "applied": applied,
            },
        },
        "error": None,
    }


CONTRACT = {
    "name": "text_normalize",
    "version": "1.0.0",
    "path": "/tools/text_normalize",
    "description": "Deterministically normalize text using explicit ops and options.",
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
                "text": {"type": "string"},
                "ops": {
                    "type": "object",
                    "properties": {
                        "normalize_newlines": {"type": "boolean"},
                        "collapse_whitespace": {"type": "boolean"},
                        "trim": {"type": "boolean"},
                        "to_lower": {"type": "boolean"},
                        "to_upper": {"type": "boolean"},
                        "remove_control_chars": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
                "options": {
                    "type": "object",
                    "properties": {
                        "preserve_tabs": {"type": "boolean"},
                        "preserve_newlines": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
            },
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
                "tool": {"type": "string"},
                "version": {"type": "string"},
                "result": {
                    "type": ["object", "null"],
                    "properties": {
                        "text": {"type": "string"},
                        "meta": {
                            "type": "object",
                            "properties": {
                                "original_length": {"type": "integer"},
                                "normalized_length": {"type": "integer"},
                                "applied": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["original_length", "normalized_length", "applied"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["text", "meta"],
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
        "envelope": {"error": {"code": "string", "message": "string", "retryable": "boolean", "details": "object"}},
        "codes": [{"code": "INPUT_INVALID", "when": "input does not match schema"}],
    },
    "non_goals": ["no advice", "no decisions", "no inference", "no external calls"],
    "examples": [
        {
            "input": {"text": "A\r\nB", "ops": {"normalize_newlines": True}},
            "output": {
                "ok": True,
                "tool": "text_normalize",
                "version": "1.0",
                "result": {
                    "text": "A\nB",
                    "meta": {"original_length": 4, "normalized_length": 3, "applied": ["normalize_newlines"]},
                },
                "error": None,
            },
        }
    ],
}
