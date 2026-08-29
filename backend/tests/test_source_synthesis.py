from app.models import ExtractionStatus, SourceStance, Verdict
from app.services.evidence_types import EvidenceHit
from app.services.source_synthesis import best_passage, classify_passage_stance, synthesize_sources
from app.services.url_extractor import ExtractedPage


CLAIM = "The Great Wall of China is visible from the Moon with the naked eye."


def _hit(url: str, *, quality: float = 0.9, authority: float = 0.9, relevance: float = 0.9) -> EvidenceHit:
    return EvidenceHit(
        title="Great Wall visibility",
        url=url,
        source_type="web_search",
        quality_score=quality,
        authority_score=authority,
        relevance_score=relevance,
    )


def _page(url: str, text: str) -> ExtractedPage:
    return ExtractedPage(
        requested_url=url,
        final_url=url,
        status=ExtractionStatus.ACCESSED,
        title="Source",
        text=text,
    )


def test_best_passage_finds_direct_claim_sentence() -> None:
    text = (
        "This page discusses many objects observed from orbit. "
        "The Great Wall of China is not visible from the Moon with the naked eye. "
        "Other structures can be photographed with optical equipment."
    )
    passage, relevance = best_passage(CLAIM, text)
    assert passage is not None
    assert "not visible from the Moon" in passage
    assert relevance >= 0.9


def test_explicit_opposite_polarity_is_contradiction() -> None:
    passage = "The Great Wall of China is not visible from the Moon with the naked eye."
    stance, confidence = classify_passage_stance(CLAIM, passage, 1.0)
    assert stance == SourceStance.CONTRADICTS
    assert confidence >= 0.9


def test_two_independent_strong_contradictions_can_produce_false() -> None:
    hits = [
        _hit("https://www.nasa.gov/great-wall", authority=0.97),
        _hit("https://pmc.ncbi.nlm.nih.gov/articles/PMC123/", authority=0.88),
    ]
    pages = {
        hits[0].url: _page(hits[0].url, "The Great Wall of China is not visible from the Moon with the naked eye."),
        hits[1].url: _page(hits[1].url, "The Great Wall of China cannot be seen from the Moon with the naked eye."),
    }

    verdict, confidence, inspected, conflicting = synthesize_sources(CLAIM, hits, fetcher=lambda url: pages[url])
    assert verdict == Verdict.FALSE
    assert confidence > 0.8
    assert conflicting is False
    assert all(hit.stance == SourceStance.CONTRADICTS for hit in inspected)


def test_two_independent_strong_supports_can_produce_verified() -> None:
    claim = "The ministry announced a new youth grant on Monday."
    hits = [
        _hit("https://ministry.gov.ng/grant", authority=0.97),
        _hit("https://reuters.com/example-grant", authority=0.79),
    ]
    pages = {
        hits[0].url: _page(hits[0].url, "The ministry announced a new youth grant on Monday for eligible applicants."),
        hits[1].url: _page(hits[1].url, "The ministry announced a new youth grant on Monday, according to its official notice."),
    }

    verdict, _, inspected, conflicting = synthesize_sources(claim, hits, fetcher=lambda url: pages[url])
    assert verdict == Verdict.VERIFIED
    assert conflicting is False
    assert all(hit.stance == SourceStance.SUPPORTS for hit in inspected)


def test_conflicting_explicit_sources_fail_safe() -> None:
    hits = [
        _hit("https://agency.gov.ng/claim", authority=0.97),
        _hit("https://example.edu/research", authority=0.84),
    ]
    pages = {
        hits[0].url: _page(hits[0].url, "The Great Wall of China is visible from the Moon with the naked eye."),
        hits[1].url: _page(hits[1].url, "The Great Wall of China is not visible from the Moon with the naked eye."),
    }

    verdict, confidence, _, conflicting = synthesize_sources(CLAIM, hits, fetcher=lambda url: pages[url])
    assert verdict == Verdict.UNVERIFIED
    assert confidence == 0.0
    assert conflicting is True


def test_weak_or_unrelated_pages_remain_unverified() -> None:
    hits = [
        _hit("https://one.example/article"),
        _hit("https://two.example/article"),
    ]
    pages = {
        hits[0].url: _page(hits[0].url, "Astronauts take photographs of cities and oceans from orbit."),
        hits[1].url: _page(hits[1].url, "China has many historic landmarks visited by tourists."),
    }

    verdict, confidence, inspected, conflicting = synthesize_sources(CLAIM, hits, fetcher=lambda url: pages[url])
    assert verdict == Verdict.UNVERIFIED
    assert confidence == 0.0
    assert conflicting is False
    assert all(hit.stance == SourceStance.UNCLEAR for hit in inspected)
