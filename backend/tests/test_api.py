from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unconnected_verifier_fails_safe() -> None:
    response = client.post(
        "/api/v1/verify",
        json={"content": "A viral claim that needs checking", "input_type": "text"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "UNVERIFIED"
    assert body["confidence"] == 0.0
    assert body["evidence"] == []
    assert body["warnings"]


def test_empty_content_is_rejected() -> None:
    response = client.post("/api/v1/verify", json={"content": ""})
    assert response.status_code == 422
