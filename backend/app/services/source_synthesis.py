from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import urlparse

from app.models import ExtractionStatus, SourceStance, Verdict
from app.services.evidence_types import EvidenceHit
from app.services.source_ranker import lexical_relevance
from app.services.url_extractor import ExtractedPage, fetch_url


NEGATION_RE = re.compile(
    r"\b(?:no|not|never|cannot|can't|cant|couldn't|couldnt|isn't|isnt|aren't|arent|"
    r"wasn't|wasnt|weren't|werent|won't|wont|without|impossible|false|myth|incorrect)\b",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\s*[\n\r]+\s*", cleaned)
    return [part.strip() for part in parts if len(part.strip()) >= 20]


def _is_negated(text: str) -> bool:
    return bool(NEGATION_RE.search(text or ""))


def best_passage(claim: str, text: str, *, max_sentences: int = 2) -> tuple[str | None, float]:
    """Return the most claim-relevant sentence window from fetched source text."""

    scored: list[tuple[float, str]] = []
    sentences = _sentences(text)
    for index, sentence in enumerate(sentences):
        score = lexical_relevance(claim, sentence, None)
        if index + 1 < len(sentences):
            pair = f"{sentence} {sentences[index + 1]}"
            pair_score = lexical_relevance(claim, pair, None)
            if pair_score > score:
                scored.append((pair_score, pair))
        scored.append((score, sentence))

    if not scored:
        return None, 0.0
    score, passage = max(scored, key=lambda item: item[0])
    if score < 0.45:
        return None, round(score, 4)

    if max_sentences <= 1:
        passage = re.split(r"(?<=[.!?])\s+", passage, maxsplit=1)[0]
    return passage[:1800], round(score, 4)


def classify_passage_stance(claim: str, passage: str | None, relevance: float) -> tuple[SourceStance, float]:
    """Classify only explicit, high-overlap support/contradiction.

    This intentionally does not attempt general natural-language inference. If the
    claim and passage do not strongly overlap, or their polarity cannot be compared
    safely, the stance remains UNCLEAR.
    """

    if not passage or relevance < 0.62:
        return SourceStance.UNCLEAR, 0.0

    claim_negated = _is_negated(claim)
    passage_negated = _is_negated(passage)

    # Require stronger overlap before using polarity as a stance signal. This avoids
    # turning a loosely related negative sentence into a contradiction.
    if relevance < 0.72:
        return SourceStance.UNCLEAR, 0.0

    stance = SourceStance.SUPPORTS if claim_negated == passage_negated else SourceStance.CONTRADICTS
    confidence = min(0.97, 0.58 + 0.39 * relevance)
    return stance, round(confidence, 4)


def _domain_key(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def inspect_source(claim: str, hit: EvidenceHit, *, fetcher=fetch_url) -> EvidenceHit:
    try:
        page: ExtractedPage = fetcher(hit.url)
    except Exception:
        return replace(hit, stance=SourceStance.UNCLEAR, stance_score=0.0)

    if page.status not in {ExtractionStatus.ACCESSED, ExtractionStatus.PARTIAL} or not page.text:
        return replace(hit, stance=SourceStance.UNCLEAR, stance_score=0.0)

    passage, passage_relevance = best_passage(claim, page.text)
    stance, stance_score = classify_passage_stance(claim, passage, passage_relevance)
    return replace(
        hit,
        passage=passage,
        passage_relevance=passage_relevance,
        stance=stance,
        stance_score=stance_score,
    )


def synthesize_sources(
    claim: str,
    ranked_hits: list[EvidenceHit],
    *,
    fetcher=fetch_url,
    max_sources: int = 4,
) -> tuple[Verdict, float, list[EvidenceHit], bool]:
    """Inspect strong candidate pages and derive a conservative evidence consensus."""

    candidates: list[EvidenceHit] = []
    seen_domains: set[str] = set()
    for hit in ranked_hits:
        if (hit.quality_score or 0.0) < 0.62 or (hit.relevance_score or 0.0) < 0.55:
            continue
        domain = _domain_key(hit.url)
        if domain and domain in seen_domains:
            continue
        if domain:
            seen_domains.add(domain)
        candidates.append(hit)
        if len(candidates) >= max_sources:
            break

    inspected = [inspect_source(claim, hit, fetcher=fetcher) for hit in candidates]
    decisive = [hit for hit in inspected if hit.stance in {SourceStance.SUPPORTS, SourceStance.CONTRADICTS}]
    if len(decisive) < 2:
        return Verdict.UNVERIFIED, 0.0, inspected, False

    support_weight = 0.0
    contradict_weight = 0.0
    for hit in decisive:
        weight = (hit.quality_score or 0.0) * (hit.stance_score or 0.0)
        if hit.stance == SourceStance.SUPPORTS:
            support_weight += weight
        elif hit.stance == SourceStance.CONTRADICTS:
            contradict_weight += weight

    total = support_weight + contradict_weight
    if total <= 0:
        return Verdict.UNVERIFIED, 0.0, inspected, False

    stronger = max(support_weight, contradict_weight)
    weaker = min(support_weight, contradict_weight)
    ratio = stronger / total
    conflicting = weaker >= 0.45 or ratio < 0.78
    if conflicting:
        return Verdict.UNVERIFIED, 0.0, inspected, True

    strong_authority_present = any((hit.authority_score or 0.0) >= 0.84 for hit in decisive)
    if stronger < 1.15 or not strong_authority_present:
        return Verdict.UNVERIFIED, 0.0, inspected, False

    verdict = Verdict.VERIFIED if support_weight > contradict_weight else Verdict.FALSE
    confidence = min(0.95, 0.58 + 0.20 * ratio + 0.06 * min(len(decisive), 3))
    return verdict, round(confidence, 3), inspected, False
