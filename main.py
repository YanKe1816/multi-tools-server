from fastapi import FastAPI
from tools.verify_test import router as verify_router
from tools.text_normalize import router as text_normalize_router
from tools.schema_validate import router as schema_validate_router
from tools.schema_map import router as schema_map_router
from tools.input_gate import router as input_gate_router
from tools.structured_error import router as structured_error_router
from tools.capability_contract import router as capability_contract_router
from tools.rule_trace import router as rule_trace_router
from tools.schema_diff import router as schema_diff_router
from tools.enum_registry import router as enum_registry_router
from tools._shared.contracts import CONTRACTS, contract_summaries
from tools._shared.errors import make_error

app = FastAPI(title="Multi-Tools Server")

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
