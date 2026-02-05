import asyncio
import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, ValidationError

from tools.verify_test import router as verify_router, verify_test as verify_test_tool
from tools.text_normalize import router as text_normalize_router, text_normalize as text_normalize_tool
from tools.schema_validate import router as schema_validate_router, schema_validate as schema_validate_tool
from tools.schema_map import router as schema_map_router, schema_map as schema_map_tool
from tools.input_gate import router as input_gate_router, input_gate as input_gate_tool
from tools.structured_error import router as structured_error_router, structured_error as structured_error_tool
from tools.capability_contract import router as capability_contract_router, capability_contract as capability_contract_tool
from tools.rule_trace import router as rule_trace_router, rule_trace as rule_trace_tool
from tools.schema_diff import router as schema_diff_router, schema_diff as schema_diff_tool
from tools.enum_registry import router as enum_registry_router, enum_registry as enum_registry_tool

from tools._shared.contracts import CONTRACTS, contract_summaries
from tools._shared.errors import make_error

app = FastAPI(title="Multi-Tools Server")

SERVER_NAME = "multi-tools-server"
SERVER_VERSION = "1.0.0"

TOOL_ORDER = [
    "verify_test",
    "text_normalize",
    "input_gate",
    "schema_validate",
    "schema_map",
    "structured_error",
    "capability_contract",
    "rule_trace",
    "schema_diff",
    "enum_registry",
]

missing_contracts = sorted(name for name in TOOL_ORDER if name not in CONTRACTS)
if missing_contracts:
    raise RuntimeError(f"Missing contracts for tools: {', '.join(missing_contracts)}")

_extra_tools = sorted(name for name in CONTRACTS.keys() if name not in TOOL_ORDER)


def _tool_entry(contract: dict) -> dict:
    name = contract["name"]
    return {
        "name": name,
        "path": contract["path"],
        "version": contract["version"],
        "description": contract["description"],
        "contract_url": f"/contracts/{name}",
    }


def _tools_manifest() -> list[dict]:
    ordered_names = [*TOOL_ORDER, *_extra_tools]
    return [_tool_entry(CONTRACTS[name]) for name in ordered_names]


# Existing tool routes (HTTP)
app.include_router(verify_router)
app.include_router(text_normalize_router)
app.include_router(schema_validate_router)
app.include_router(schema_map_router)
app.include_router(input_gate_router)
app.include_router(structured_error_router)
app.include_router(capability_contract_router)
app.include_router(rule_trace_router)
app.include_router(schema_diff_router)
app.include_router(enum_registry_router)


# Internal dispatch (no HTTP self-calls)
TOOL_HANDLERS = {
    "verify_test": verify_test_tool,
    "text_normalize": text_normalize_tool,
    "schema_validate": schema_validate_tool,
    "schema_map": schema_map_tool,
    "input_gate": input_gate_tool,
    "structured_error": structured_error_tool,
    "capability_contract": capability_contract_tool,
    "rule_trace": rule_trace_tool,
    "schema_diff": schema_diff_tool,
    "enum_registry": enum_registry_tool,
}


class MessageInput(BaseModel):
    tool: str
    input: dict[str, Any]
    request_id: str

    class Config:
        extra = "forbid"


def _message_error(
    request_id: str,
    tool: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "tool": tool,
        "ok": False,
        "error": {"code": code, "message": message, "details": details or {}},
    }


async def _sse_stream():
    yield "event: hello\ndata: {}\n\n"
    while True:
        await asyncio.sleep(15)
        yield "event: ping\ndata: {}\n\n"


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "server is running",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "tool_manifest": "/mcp",
    }


@app.get("/mcp")
def get_manifest():
    return {"tools": _tools_manifest(), "contracts": "/contracts"}


@app.get("/connect")
def connect():
    return {
        "server_name": SERVER_NAME,
        "server_version": SERVER_VERSION,
        "sse_url": "/sse",
        "tools_url": "/mcp",
    }


@app.get("/sse")
def sse():
    return StreamingResponse(_sse_stream(), media_type="text/event-stream")


@app.post("/message")
def message(payload: dict[str, Any]):
    try:
        data = MessageInput.model_validate(payload)
    except ValidationError:
        return _message_error("", "", "INPUT_INVALID", "Input must match the message schema.")

    handler = TOOL_HANDLERS.get(data.tool)
    if not handler:
        return _message_error(data.request_id, data.tool, "TOOL_NOT_FOUND", "Tool not found.")

    result = handler(data.input)

    if isinstance(result, JSONResponse):
        body = result.body.decode("utf-8") if result.body else ""
        output = json.loads(body) if body else None
        if result.status_code >= 400:
            return _message_error(
                data.request_id,
                data.tool,
                "TOOL_INPUT_INVALID",
                "Tool returned an error.",
                {"status_code": result.status_code, "output": output},
            )
        return {"request_id": data.request_id, "tool": data.tool, "output": output, "ok": True}

    return {"request_id": data.request_id, "tool": data.tool, "output": result, "ok": True}


@app.get("/contracts")
def list_contracts():
    return {"contracts": contract_summaries()}


def _get_contract_or_error(name: str):
    contract = CONTRACTS.get(name)
    if not contract:
        response = make_error("CONTRACT_NOT_FOUND", "Contract not found.")
        response.status_code = 404
        return response
    return contract


@app.get("/contracts/{name}")
def get_contract(name: str):
    return _get_contract_or_error(name)


@app.get("/tools/{name}/contract")
def get_tool_contract(name: str):
    return _get_contract_or_error(name)
