from app.services.evidence_provider import get_configured_evidence_provider, register_evidence_provider


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
