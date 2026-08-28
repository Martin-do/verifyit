from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _clear_provider(monkeypatch) -> None:
    monkeypatch.delenv("VERIFYIT_EVIDENCE_PROVIDER", raising=False)
    monkeypatch.delenv("VERIFYIT_GOOGLE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_FACT_CHECK_API_KEY", raising=False)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unconfigured_verifier_fails_safe(monkeypatch) -> None:
    _clear_provider(monkeypatch)
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
    assert "Google" not in " ".join(body["warnings"])
    assert body["detected_input_type"] == "text"


def test_auto_detects_url_without_fetching_private_target(monkeypatch) -> None:
    _clear_provider(monkeypatch)
    response = client.post(
        "/api/v1/verify",
        json={"content": "http://127.0.0.1/private", "input_type": "auto"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["detected_input_type"] == "url"
    assert body["extraction_status"] == "rejected"
    assert body["verdict"] == "UNVERIFIED"


def test_empty_content_is_rejected() -> None:
    response = client.post("/api/v1/verify", json={"content": ""})
    assert response.status_code == 422
