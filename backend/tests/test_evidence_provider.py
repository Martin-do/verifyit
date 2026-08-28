from app.services.evidence_provider import (
    GoogleFactCheckProvider,
    get_configured_evidence_provider,
    register_evidence_provider,
)


class DemoProvider:
    provider_id = "demo"

    def search(self, query: str, context: str):
        return []


def test_custom_provider_can_be_registered(monkeypatch) -> None:
    register_evidence_provider("demo", lambda: DemoProvider())
    monkeypatch.setenv("VERIFYIT_EVIDENCE_PROVIDER", "demo")
    provider = get_configured_evidence_provider()
    assert provider is not None
    assert provider.provider_id == "demo"


def test_blank_provider_keeps_evidence_disabled(monkeypatch) -> None:
    monkeypatch.delenv("VERIFYIT_EVIDENCE_PROVIDER", raising=False)
    monkeypatch.setenv("VERIFYIT_GOOGLE_ACCESS_TOKEN", "unused-token")
    assert get_configured_evidence_provider() is None


def test_google_provider_can_use_short_lived_oauth_token(monkeypatch) -> None:
    monkeypatch.setenv("VERIFYIT_EVIDENCE_PROVIDER", "google_factcheck")
    monkeypatch.setenv("VERIFYIT_GOOGLE_ACCESS_TOKEN", "temporary-oauth-token")
    provider = get_configured_evidence_provider()
    assert isinstance(provider, GoogleFactCheckProvider)
    assert provider.access_token == "temporary-oauth-token"
