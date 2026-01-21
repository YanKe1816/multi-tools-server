from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


class Capability(BaseModel):
    name: str
    path: str
    version: str


class ContractInputs(BaseModel):
    schema: Any


class ContractOutputs(BaseModel):
    schema: Any


class ContractForbidden(BaseModel):
    network: bool = True
    storage: bool = True
    side_effects: bool = True
    judgement: bool = True


class ContractBehavior(BaseModel):
    deterministic: bool = True
    idempotent: bool = True


class Contract(BaseModel):
    inputs: ContractInputs
    outputs: ContractOutputs
    forbidden: ContractForbidden = ContractForbidden()
    behavior: ContractBehavior = ContractBehavior()


class Input(BaseModel):
    capability: Capability
    contract: Contract
    mode: str = "validate"


def _is_object(value: Any) -> bool:
    return isinstance(value, dict)


def _normalize_contract(contract: Contract) -> dict[str, Any]:
    payload = contract.model_dump()
    return json.loads(json.dumps(payload, sort_keys=True))


@router.post("/tools/capability_contract")
def capability_contract(payload: Input):
    if payload.mode not in {"validate", "normalize"}:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "MODE_INVALID", "message": "Mode must be validate or normalize."}},
        )

    if not _is_object(payload.contract.inputs.schema):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "SCHEMA_INVALID",
                    "message": "contract.inputs.schema must be an object.",
                }
            },
        )
    if not _is_object(payload.contract.outputs.schema):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "SCHEMA_INVALID",
                    "message": "contract.outputs.schema must be an object.",
                }
            },
        )

    errors: list[dict[str, str]] = []
    forbidden = payload.contract.forbidden
    forbidden_map = {
        "network": forbidden.network,
        "storage": forbidden.storage,
        "side_effects": forbidden.side_effects,
        "judgement": forbidden.judgement,
    }
    for field, value in forbidden_map.items():
        if value is False:
            errors.append(
                {
                    "path": f"contract.forbidden.{field}",
                    "code": "FORBIDDEN_VIOLATION",
                    "message": "Forbidden flag must be true.",
                }
            )

    if payload.contract.behavior.deterministic is not True:
        errors.append(
            {
                "path": "contract.behavior.deterministic",
                "code": "BEHAVIOR_NON_DETERMINISTIC",
                "message": "Behavior must be deterministic.",
            }
        )

    if errors:
        return {"ok": False, "errors": errors}

    normalized = _normalize_contract(payload.contract) if payload.mode == "normalize" else payload.contract.model_dump()
    return {"ok": True, "contract": normalized}
