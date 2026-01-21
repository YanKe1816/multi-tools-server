from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_text_normalize_empty_text():
    response = client.post("/tools/text_normalize", json={"text": ""})
    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "TEXT_EMPTY",
            "message": "Text is empty.",
            "retryable": False,
            "details": {},
        }
    }


def test_text_normalize_too_long():
    response = client.post("/tools/text_normalize", json={"text": "a" * 20001})
    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "TEXT_TOO_LONG",
            "message": "Text exceeds 20000 characters.",
            "retryable": False,
            "details": {},
        }
    }


def test_text_normalize_invalid_mode():
    response = client.post("/tools/text_normalize", json={"text": "ok", "mode": "other"})
    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "MODE_INVALID",
            "message": "Mode must be basic or strict.",
            "retryable": False,
            "details": {},
        }
    }
