from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import urlparse

from app.models import ExtractionStatus, SourceStance, Verdict
from app.services.evidence_types import EvidenceHit
from app.services.source_ranker import lexical_relevance
from app.services.url_extractor import ExtractedPage, fetch_url


DIRECT_NEGATION_RE = re.compile(
    r"\b(?:no|not|never|cannot|can't|cant|couldn't|couldnt|isn't|isnt|aren't|arent|"
    r"wasn't|wasnt|weren't|werent|won't|wont|without|impossible)\b",
    re.IGNORECASE,
)

REFUTATION_RE = re.compile(
    r"\b(?:myth|misconception|false|incorrect|untrue|baseless|bogus|hoax|debunked|"
    r"disproved|refuted)\b|\bnot\s+true\b",
    re.IGNORECASE,
)

# Useful when selecting what to display, but deliberately not sufficient by itself to
# make a stance decisive. Phrases such as "less likely" are informative answers yet
# are weaker than an explicit "cannot" or "not" for verdict synthesis.
QUALIFIED_ANSWER_RE = re.compile(
    r"\b(?:unlikely|less\s+likely|highly\s+unlikely|doubtful)\b|\banswer\b.{0,40}\bno\b",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [part.strip() for part in parts if len(part.strip()) >= 20]


def _is_negated(text: str) -> bool:
    return bool(DIRECT_NEGATION_RE.search(text or ""))


def _has_refutation(text: str) -> bool:
    return bool(REFUTATION_RE.search(text or ""))


def _has_selection_signal(text: str) -> bool:
    return _is_negated(text) or _has_refutation(text) or bool(QUALIFIED_ANSWER_RE.search(text or ""))


def _starts_with_question(text: str) -> bool:
    candidate = (text or "").strip()
    if not candidate:
        return False
    question_at = candidate.find("?")
    return 0 <= question_at < min(len(candidate), 220)


def _question_only(text: str) -> bool:
    candidate = (text or "").strip()
    if not candidate:
        return False
    sentences = _sentences(candidate)
    return bool(sentences) and all(sentence.rstrip().endswith("?") for sentence in sentences)


def _passage_selection_score(claim: str, passage: str) -> tuple[float, float]:
    """Score passage selection separately from the relevance value exposed downstream.

    Search/article titles often repeat a claim verbatim as a question. They are highly
    lexically relevant but contain no answer. Prefer substantive declarative windows,
    especially those carrying answer/refutation language, without changing the
    underlying claim-overlap score used by the stance classifier.
    """

    relevance = lexical_relevance(claim, passage, None)
    selection_signal = _has_selection_signal(passage)

    score = relevance
    if selection_signal:
        score += 0.18

    word_count = len(re.findall(r"[a-z0-9]+", passage.lower()))
    if word_count >= 18:
        score += 0.04

    if _question_only(passage):
        score -= 0.30
    elif _starts_with_question(passage) and not selection_signal:
        score -= 0.38

    return score, relevance


def best_passage(claim: str, text: str, *, max_sentences: int = 2) -> tuple[str | None, float]:
    """Return the most claim-relevant substantive sentence window from fetched text."""

    sentences = _sentences(text)
    if not sentences:
        return None, 0.0

    scored: list[tuple[float, float, str]] = []
    window_size = max(1, min(max_sentences, 3))

    for index in range(len(sentences)):
        for size in range(1, window_size + 1):
            if index + size > len(sentences):
                break
            passage = " ".join(sentences[index : index + size])
            selection_score, relevance = _passage_selection_score(claim, passage)
            scored.append((selection_score, relevance, passage))

    selection_score, relevance, passage = max(
        scored,
        key=lambda item: (item[0], item[1], len(item[2])),
    )
    if relevance < 0.40:
        return None, round(relevance, 4)

    return passage[:1800], round(relevance, 4)


def classify_passage_stance(claim: str, passage: str | None, relevance: float) -> tuple[SourceStance, float]:
    """Classify only explicit, high-overlap support/contradiction.

    This intentionally does not attempt general natural-language inference. If the
    claim and passage do not strongly overlap, or their polarity cannot be compared
    safely, the stance remains UNCLEAR.
    """

    if not passage or relevance < 0.62:
        return SourceStance.UNCLEAR, 0.0

    if _question_only(passage):
        return SourceStance.UNCLEAR, 0.0

    # Require stronger overlap before using polarity/refutation as a stance signal.
    if relevance < 0.72:
        return SourceStance.UNCLEAR, 0.0

    claim_negated = _is_negated(claim)

    if _has_refutation(passage):
        # Refutation language reverses the proposition it targets. Remove those cue
        # words before checking whether the embedded proposition itself is negated.
        embedded = REFUTATION_RE.sub(" ", passage)
        embedded_negated = _is_negated(embedded)
        stance = SourceStance.CONTRADICTS if claim_negated == embedded_negated else SourceStance.SUPPORTS
    else:
        passage_negated = _is_negated(passage)
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
