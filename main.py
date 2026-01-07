from fastapi import FastAPI
from tools.verify_test import router as verify_router

app = FastAPI(title="Multi-Tools Server")

app.include_router(verify_router)


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "server is running",
        "hint": "try POST /tools/verify_test",
    }
