from fastapi.testclient import TestClient

from main import TOOLS, app

client = TestClient(app)


def test_contracts_list_contains_all_tools():
    response = client.get("/contracts")
    assert response.status_code == 200
    payload = response.json()
    names = {item["name"] for item in payload["contracts"]}
    tool_names = {tool["name"] for tool in TOOLS}
    assert tool_names == names


def test_text_normalize_contract_has_required_keys():
    response = client.get("/contracts/text_normalize")
    assert response.status_code == 200
    contract = response.json()
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
    assert {"TEXT_EMPTY", "TEXT_TOO_LONG", "MODE_INVALID"} <= codes


def test_contract_not_found():
    response = client.get("/contracts/does_not_exist")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "CONTRACT_NOT_FOUND",
            "message": "Contract not found.",
            "retryable": False,
            "details": {},
        }
    }


def test_tool_contract_matches_registry():
    contract_response = client.get("/contracts/text_normalize")
    tool_response = client.get("/tools/text_normalize/contract")
    assert contract_response.status_code == 200
    assert tool_response.status_code == 200
    assert tool_response.json() == contract_response.json()
