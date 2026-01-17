from fastapi import FastAPI
from tools.verify_test import router as verify_router
from tools.text_normalize import router as text_normalize_router

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
]

app.include_router(verify_router)
app.include_router(text_normalize_router)


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
