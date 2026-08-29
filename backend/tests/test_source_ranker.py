from datetime import datetime, timezone

from app.services.evidence_types import EvidenceHit
from app.services.source_ranker import classify_source, freshness_score, rank_evidence


def test_government_source_has_higher_authority_than_social() -> None:
    gov_label, gov_score = classify_source("https://www.cbn.gov.ng/press/")
    social_label, social_score = classify_source("https://www.facebook.com/example")
    assert gov_label == "official government source"
    assert social_label == "social platform"
    assert gov_score > social_score


def test_primary_authority_can_outrank_generic_repost() -> None:
    hits = [
        EvidenceHit(
            title="Federal grant announcement",
            url="https://randomblog.example/grant",
            source_type="web_search",
            snippet="Federal government youth grant announcement",
            provider_score=0.95,
        ),
        EvidenceHit(
            title="Federal grant announcement",
            url="https://example.gov.ng/grant",
            source_type="web_search",
            snippet="Federal government youth grant announcement",
            provider_score=0.80,
        ),
    ]
    ranked = rank_evidence(hits, "Federal government youth grant announcement")
    assert ranked[0].url == "https://example.gov.ng/grant"
    assert (ranked[0].authority_score or 0) > (ranked[1].authority_score or 0)


def test_freshness_is_small_and_bounded() -> None:
    now = datetime(2026, 8, 29, tzinfo=timezone.utc)
    assert freshness_score("2026-08-28T10:00:00+00:00", now=now) == 1.0
    assert 0.0 <= freshness_score(None, now=now) <= 1.0
