import asyncio
import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from tools.verify_test import router as verify_router, verify_test as verify_test_tool
from tools.text_normalize import router as text_normalize_router
from tools.schema_validate import router as schema_validate_router
from tools.schema_map import router as schema_map_router
from tools.input_gate import router as input_gate_router
from tools.structured_error import router as structured_error_router
from tools.capability_contract import router as capability_contract_router
from tools.rule_trace import router as rule_trace_router
from tools.schema_diff import router as schema_diff_router
from tools.enum_registry import router as enum_registry_router
from tools.text_normalize import text_normalize as text_normalize_tool
from tools.schema_validate import schema_validate as schema_validate_tool
from tools.schema_map import schema_map as schema_map_tool
from tools.input_gate import input_gate as input_gate_tool
from tools.structured_error import structured_error as structured_error_tool
from tools.capability_contract import capability_contract as capability_contract_tool
from tools.rule_trace import rule_trace as rule_trace_tool
from tools.schema_diff import schema_diff as schema_diff_tool
from tools.enum_registry import enum_registry as enum_registry_tool
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


def _tool_entry(contract: dict[str, Any]) -> dict[str, Any]:
    name = contract["name"]
    return {
        "name": name,
        "path": contract["path"],
        "version": contract["version"],
        "description": contract["description"],
        "contract_url": f"/contracts/{name}",
    }


def _tools_manifest() -> list[dict[str, Any]]:
    ordered_names = [*TOOL_ORDER, *_extra_tools]
    return [_tool_entry(CONTRACTS[name]) for name in ordered_names]


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


def _message_error(request_id: str | int | None, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
            "data": details or {},
        },
    }


def _legacy_message_error(request_id: str, tool: str, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "tool": tool,
        "ok": False,
        "error": {"code": code, "message": message, "details": details or {}},
    }


def _json_response_payload(result: JSONResponse) -> Any:
    body = result.body.decode("utf-8") if result.body else ""
    return json.loads(body) if body else None


def _invoke_tool(tool_name: str, tool_input: dict[str, Any]) -> tuple[bool, Any, dict[str, Any] | None]:
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return False, None, {"code": "TOOL_NOT_FOUND", "message": "Tool not found.", "details": {"tool": tool_name}}

    result = handler(tool_input)
    if isinstance(result, JSONResponse):
        output = _json_response_payload(result)
        if result.status_code >= 400:
            return (
                False,
                None,
                {
                    "code": "TOOL_INPUT_INVALID",
                    "message": "Tool returned an error.",
                    "details": {"status_code": result.status_code, "output": output},
                },
            )
        return True, output, None

    return True, result, None


def _tools_list_payload() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for tool in _tools_manifest():
        contract = CONTRACTS[tool["name"]]
        input_schema = contract.get("inputs", {}).get("json_schema", {"type": "object", "additionalProperties": True})
        tools.append(
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": input_schema,
            }
        )
    return tools


async def _sse_stream(base_url: str):
    endpoint_url = f"{base_url.rstrip('/')}/message"
    yield f"event: endpoint\ndata: {endpoint_url}\n\n"
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
def sse(request: Request):
    return StreamingResponse(
        _sse_stream(str(request.base_url)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/message")
def message(payload: dict[str, Any]):
    if payload.get("jsonrpc") == "2.0":
        request_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "capabilities": {"tools": {"listChanged": False}},
                },
            }

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _tools_list_payload()}}

        if method == "tools/call":
            tool_name = params.get("name")
            tool_input = params.get("arguments")
            if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
                return _message_error(request_id, "INVALID_PARAMS", "tools/call requires name and arguments object.")

            ok, output, error = _invoke_tool(tool_name, tool_input)
            if not ok and error:
                return _message_error(request_id, error["code"], error["message"], error["details"])

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}], "isError": False},
            }

        return _message_error(request_id, "METHOD_NOT_FOUND", "Method not found.")

    tool = payload.get("tool")
    tool_input = payload.get("input")
    request_id = payload.get("request_id", "")
    if not isinstance(tool, str) or not isinstance(tool_input, dict) or not isinstance(request_id, str):
        return _legacy_message_error("", "", "INPUT_INVALID", "Input must match the message schema.")

    ok, output, error = _invoke_tool(tool, tool_input)
    if not ok and error:
        return _legacy_message_error(request_id, tool, error["code"], error["message"], error["details"])

    return {"request_id": request_id, "tool": tool, "output": output, "ok": True}


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
