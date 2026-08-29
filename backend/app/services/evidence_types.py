from __future__ import annotations

from dataclasses import dataclass

from app.models import SourceStance, Verdict


@dataclass
class EvidenceHit:
    """Provider-neutral evidence candidate returned to the verifier."""

    title: str
    url: str
    source_type: str
    snippet: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    rating: str | None = None
    claim_text: str | None = None
    normalized_verdict: Verdict | None = None
    provider_score: float | None = None
    match_score: float | None = None
    authority_score: float | None = None
    relevance_score: float | None = None
    freshness_score: float | None = None
    quality_score: float | None = None
    source_label: str | None = None
    passage: str | None = None
    passage_relevance: float | None = None
    stance: SourceStance | None = None
    stance_score: float | None = None
