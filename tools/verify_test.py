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
