from __future__ import annotations

from tools.capability_contract import CONTRACT as CAPABILITY_CONTRACT_CONTRACT
from tools.enum_registry import CONTRACT as ENUM_REGISTRY_CONTRACT
from tools.input_gate import CONTRACT as INPUT_GATE_CONTRACT
from tools.rule_trace import CONTRACT as RULE_TRACE_CONTRACT
from tools.schema_diff import CONTRACT as SCHEMA_DIFF_CONTRACT
from tools.schema_map import CONTRACT as SCHEMA_MAP_CONTRACT
from tools.schema_validate import CONTRACT as SCHEMA_VALIDATE_CONTRACT
from tools.structured_error import CONTRACT as STRUCTURED_ERROR_CONTRACT
from tools.text_normalize import CONTRACT as TEXT_NORMALIZE_CONTRACT
from tools.verify_test import CONTRACT as VERIFY_TEST_CONTRACT

CONTRACTS = {
    contract["name"]: contract
    for contract in [
        VERIFY_TEST_CONTRACT,
        TEXT_NORMALIZE_CONTRACT,
        INPUT_GATE_CONTRACT,
        SCHEMA_VALIDATE_CONTRACT,
        SCHEMA_MAP_CONTRACT,
        STRUCTURED_ERROR_CONTRACT,
        CAPABILITY_CONTRACT_CONTRACT,
        RULE_TRACE_CONTRACT,
        SCHEMA_DIFF_CONTRACT,
        ENUM_REGISTRY_CONTRACT,
    ]
}


def contract_summaries() -> list[dict[str, str]]:
    summaries = []
    for contract in CONTRACTS.values():
        summaries.append(
            {
                "name": contract["name"],
                "version": contract["version"],
                "path": contract["path"],
                "description": contract["description"],
            }
        )
    return sorted(summaries, key=lambda item: item["name"])
