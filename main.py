from fastapi import FastAPI
from tools.verify_test import router as verify_router
from tools.text_normalize import router as text_normalize_router
from tools.schema_validate import router as schema_validate_router
from tools.schema_map import router as schema_map_router

app = FastAPI(title="Multi-Tools Server")


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
]

app.include_router(verify_router)
app.include_router(text_normalize_router)
app.include_router(schema_validate_router)
app.include_router(schema_map_router)


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
