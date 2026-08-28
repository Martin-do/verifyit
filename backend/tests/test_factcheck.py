from app.models import Verdict
from app.services.factcheck import FactCheckHit, claim_match_score, consensus_verdict, normalize_rating


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
