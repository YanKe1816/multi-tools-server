from tests.asgi_client import request_json
from main import TOOLS, app


def test_contracts_list_contains_all_tools():
    status, body = request_json(app, "GET", "/contracts")
    assert status == 200
    names = {item["name"] for item in body["contracts"]}
    tool_names = {tool["name"] for tool in TOOLS}
    assert tool_names == names


def test_text_normalize_contract_has_required_keys():
    status, contract = request_json(app, "GET", "/contracts/text_normalize")
    assert status == 200
    assert contract["name"] == "text_normalize"
    assert contract["version"] == "1.0.0"
    determinism = contract["determinism"]
    assert determinism == {
        "same_input_same_output": True,
        "side_effects": False,
        "network": False,
        "storage": False,
    }
    codes = {entry["code"] for entry in contract["errors"]["codes"]}
    assert {"INPUT_INVALID"} <= codes


def test_contract_not_found():
    status, body = request_json(app, "GET", "/contracts/does_not_exist")
    assert status == 404
    assert body == {
        "error": {
            "code": "CONTRACT_NOT_FOUND",
            "message": "Contract not found.",
            "retryable": False,
            "details": {},
        }
    }


def test_tool_contract_matches_registry():
    status_contract, contract = request_json(app, "GET", "/contracts/text_normalize")
    status_tool, tool_contract = request_json(app, "GET", "/tools/text_normalize/contract")
    assert status_contract == 200
    assert status_tool == 200
    assert tool_contract == contract
