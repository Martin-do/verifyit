from app.services.evidence_types import EvidenceHit
from app.services.source_ranker import classify_source, rank_evidence


def _hit(title: str, url: str, snippet: str, provider_score: float = 0.9) -> EvidenceHit:
    return EvidenceHit(
        title=title,
        url=url,
        snippet=snippet,
        provider_score=provider_score,
        source_kind="web_search",
    )


def test_pmc_article_is_academic_not_official_government_statement() -> None:
    label, authority = classify_source(
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/",
        title="Is it Really Possible to See the Great Wall of China from Space with a Naked Eye?",
    )
    assert label == "academic literature (government-hosted)"
    assert 0.80 <= authority < 0.97


def test_nasa_page_remains_official_government_source() -> None:
    label, authority = classify_source("https://www.nasa.gov/image-article/great-wall/")
    assert label == "official government source"
    assert authority >= 0.95


def test_provider_score_cannot_replace_claim_term_relevance() -> None:
    query = "The Great Wall of China is visible from the Moon with the naked eye"
    vague = _hit(
        "Amazing things visible from space",
        "https://example.com/space",
        "Astronauts photograph cities, roads and large structures from orbit.",
        provider_score=1.0,
    )
    direct = _hit(
        "Great Wall - NASA",
        "https://www.nasa.gov/image-article/great-wall/",
        "Despite myths to the contrary, the wall isn't visible from the moon with the naked eye.",
        provider_score=0.70,
    )

    ranked = rank_evidence([vague, direct], query)
    assert ranked[0].url == direct.url
    assert (ranked[0].relevance_score or 0) > (ranked[1].relevance_score or 0)
