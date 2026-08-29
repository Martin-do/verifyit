from app.services.evidence_provider import (
    GoogleFactCheckProvider,
    SearXNGProvider,
    TavilyProvider,
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
    monkeypatch.setenv("TAVILY_API_KEY", "unused-key")
    assert get_configured_evidence_provider() is None


def test_tavily_provider_uses_environment_key(monkeypatch) -> None:
    monkeypatch.setenv("VERIFYIT_EVIDENCE_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    provider = get_configured_evidence_provider()
    assert isinstance(provider, TavilyProvider)
    assert provider.api_key == "tvly-test"


def test_searxng_provider_uses_configured_base_url(monkeypatch) -> None:
    monkeypatch.setenv("VERIFYIT_EVIDENCE_PROVIDER", "searxng")
    monkeypatch.setenv("SEARXNG_BASE_URL", "https://search.example")
    provider = get_configured_evidence_provider()
    assert isinstance(provider, SearXNGProvider)
    assert provider.base_url == "https://search.example"


def test_google_provider_can_use_short_lived_oauth_token(monkeypatch) -> None:
    monkeypatch.setenv("VERIFYIT_EVIDENCE_PROVIDER", "google_factcheck")
    monkeypatch.setenv("VERIFYIT_GOOGLE_ACCESS_TOKEN", "temporary-oauth-token")
    provider = get_configured_evidence_provider()
    assert isinstance(provider, GoogleFactCheckProvider)
    assert provider.access_token == "temporary-oauth-token"
