import httpx
import pytest

from app.models import Verdict
from app.services.factcheck import (
    FactCheckHit,
    FactCheckProviderError,
    claim_match_score,
    consensus_verdict,
    normalize_rating,
    search_fact_checks,
)


def _hit(verdict: Verdict | None, score: float, url: str = "https://example.com/check") -> FactCheckHit:
    return FactCheckHit(
        claim_text="Government announced a new grant",
        review_title="Fact check",
        review_url=url,
        publisher="Example Fact Check",
        rating=verdict.value if verdict else None,
        review_date="2026-08-01",
        normalized_verdict=verdict,
        match_score=score,
    )


def test_rating_normalization_is_conservative() -> None:
    assert normalize_rating("False") == Verdict.FALSE
    assert normalize_rating("Missing Context") == Verdict.MISLEADING
    assert normalize_rating("We need more evidence") is None


def test_claim_match_rewards_candidate_coverage() -> None:
    score = claim_match_score(
        "Reports say the federal government announced a new youth grant today.",
        "Federal government announced a new youth grant",
    )
    assert score >= 0.7


def test_consensus_requires_agreement() -> None:
    verdict, confidence, matched, conflicting = consensus_verdict([
        _hit(Verdict.FALSE, 0.9, "https://a.example/check"),
        _hit(Verdict.FALSE, 0.8, "https://b.example/check"),
    ])
    assert verdict == Verdict.FALSE
    assert confidence > 0.8
    assert len(matched) == 2
    assert conflicting is False


def test_conflicting_ratings_fail_safe() -> None:
    verdict, confidence, _, conflicting = consensus_verdict([
        _hit(Verdict.FALSE, 0.9, "https://a.example/check"),
        _hit(Verdict.VERIFIED, 0.9, "https://b.example/check"),
    ])
    assert verdict == Verdict.UNVERIFIED
    assert confidence == 0.0
    assert conflicting is True


def test_provider_http_error_exposes_safe_detail_without_key(monkeypatch) -> None:
    request = httpx.Request(
        "GET",
        "https://factchecktools.googleapis.com/v1alpha1/claims:search?key=SUPER_SECRET_KEY",
    )
    response = httpx.Response(
        403,
        request=request,
        json={
            "error": {
                "status": "PERMISSION_DENIED",
                "message": "Fact Check Tools API has not been used in project 123 before or it is disabled.",
            }
        },
    )
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: response)

    with pytest.raises(FactCheckProviderError) as caught:
        search_fact_checks("claim", "claim", "SUPER_SECRET_KEY")

    exc = caught.value
    assert exc.status_code == 403
    assert "PERMISSION_DENIED" in (exc.detail or "")
    assert "disabled" in (exc.detail or "")
    assert "SUPER_SECRET_KEY" not in str(exc)
    assert "SUPER_SECRET_KEY" not in (exc.detail or "")
