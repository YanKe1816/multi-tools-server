from fastapi import FastAPI

from tools.verify_test import router as verify_router
from tools.text_normalize import router as text_normalize_router
from tools.schema_validate import router as schema_validate_router
from tools.schema_map import router as schema_map_router
from tools.input_gate import router as input_gate_router
from tools.structured_error import router as structured_error_router
from tools.capability_contract import router as capability_contract_router
from tools.rule_trace import router as rule_trace_router

app = FastAPI(title="Multi-Tools Server")

# SSOT for tool discovery (/mcp)
TOOLS = [
    {
        "name": "verify_test",
        "path": "/tools/verify_test",
        "description": "Echo input text and return its length. Used to verify service stability.",
    },
    {
        "name": "text_normalize",
        "path": "/tools/text_normalize",
        "description": "Deterministic text normalization (newline, whitespace, blank lines, tabs).",
    },
    {
        "name": "schema_validate",
        "path": "/tools/schema_validate",
        "description": "Deterministic validation against a limited JSON Schema subset.",
    },
    {
        "name": "schema_map",
        "path": "/tools/schema_map",
        "description": "Deterministic object mapping with rename/drop/default/require rules.",
    },
    {
        "name": "input_gate",
        "path": "/tools/input_gate",
        "description": "Pre-flight input checks for type, size, and structure constraints.",
    },
    {
        "name": "structured_error",
        "path": "/tools/structured_error",
        "description": "Normalize error inputs into a structured error envelope.",
    },
    {
        "name": "capability_contract",
        "path": "/tools/capability_contract",
        "description": "Validate or normalize a machine-readable capability contract.",
    },
    {
        "name": "rule_trace",
        "path": "/tools/rule_trace",
        "description": "Normalize execution traces with input/output summaries and rule hits.",
    },
]

# Tool routers
app.include_router(verify_router)
app.include_router(text_normalize_router)
app.include_router(schema_validate_router)
app.include_router(schema_map_router)
app.include_router(input_gate_router)
app.include_router(structured_error_router)
app.include_router(capability_contract_router)
app.include_router(rule_trace_router)


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
    return {"tools": TOOLS}
