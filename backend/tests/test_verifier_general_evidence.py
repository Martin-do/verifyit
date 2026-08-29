from app.models import InputType, VerifyRequest, Verdict
from app.services.evidence_types import EvidenceHit
from app.services import verifier


class DemoWebProvider:
    provider_id = "demo-web"

    def search(self, query: str, context: str):
        return [
            EvidenceHit(
                title="Official announcement",
                url="https://example.gov.ng/announcement",
                source_type="web_search",
                snippet="The government published an announcement related to the claim.",
                provider_score=0.9,
            )
        ]


def test_web_search_returns_ranked_evidence_without_guessing(monkeypatch) -> None:
    monkeypatch.setattr(verifier, "get_configured_evidence_provider", lambda: DemoWebProvider())
    response = verifier.verify(VerifyRequest(content="Government announced a new grant", input_type=InputType.TEXT))

    assert response.verdict == Verdict.UNVERIFIED
    assert response.confidence == 0.0
    assert len(response.evidence) == 1
    assert response.evidence[0].source_label == "official government source"
    assert response.evidence[0].quality_score is not None
    assert any("snippets alone" in warning for warning in response.warnings)
