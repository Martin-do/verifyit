from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

import httpx

from app.models import Verdict


FACTCHECK_ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from", "has", "have", "in",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "were", "will", "with",
}


class FactCheckProviderError(RuntimeError):
    pass


@dataclass
class FactCheckHit:
    claim_text: str
    review_title: str
    review_url: str
    publisher: str | None
    rating: str | None
    review_date: str | None
    normalized_verdict: Verdict | None
    match_score: float = 0.0


def _normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _tokens(value: str) -> set[str]:
    return {token for token in _normalized_text(value).split() if token not in STOP_WORDS and len(token) > 1}


def claim_match_score(context: str, candidate_claim: str) -> float:
    left = _normalized_text(context)
    right = _normalized_text(candidate_claim)
    if not left or not right:
        return 0.0

    sequence = SequenceMatcher(None, left[:1200], right[:1200]).ratio()
    context_tokens = _tokens(context)
    claim_tokens = _tokens(candidate_claim)
    if not claim_tokens:
        return sequence

    overlap = len(context_tokens & claim_tokens)
    coverage = overlap / len(claim_tokens)
    union = len(context_tokens | claim_tokens)
    jaccard = overlap / union if union else 0.0
    token_score = 0.8 * coverage + 0.2 * jaccard
    return round(max(sequence, token_score), 4)


def normalize_rating(value: str | None) -> Verdict | None:
    if not value:
        return None

    rating = _normalized_text(value)
    exact = {
        "true": Verdict.VERIFIED,
        "correct": Verdict.VERIFIED,
        "accurate": Verdict.VERIFIED,
        "mostly true": Verdict.MOSTLY_TRUE,
        "false": Verdict.FALSE,
        "incorrect": Verdict.FALSE,
        "fake": Verdict.FALSE,
        "hoax": Verdict.FALSE,
        "pants on fire": Verdict.FALSE,
        "misleading": Verdict.MISLEADING,
        "missing context": Verdict.MISLEADING,
        "partly false": Verdict.MISLEADING,
        "partially false": Verdict.MISLEADING,
        "mostly false": Verdict.MISLEADING,
        "half true": Verdict.MISLEADING,
        "mixture": Verdict.MISLEADING,
        "scam": Verdict.SCAM_RISK,
    }
    if rating in exact:
        return exact[rating]

    if "scam" in rating or "fraud" in rating:
        return Verdict.SCAM_RISK
    if "mostly true" in rating:
        return Verdict.MOSTLY_TRUE
    if any(term in rating for term in ("misleading", "missing context", "partly false", "partially false", "mostly false")):
        return Verdict.MISLEADING
    if rating.startswith("false") or rating.endswith(" false"):
        return Verdict.FALSE
    return None


def search_fact_checks(query: str, context: str, api_key: str, page_size: int = 8) -> list[FactCheckHit]:
    params = {
        "query": " ".join(query.split())[:500],
        "pageSize": max(1, min(page_size, 20)),
        "key": api_key,
    }

    try:
        response = httpx.get(FACTCHECK_ENDPOINT, params=params, timeout=8.0, follow_redirects=False)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise FactCheckProviderError("Google Fact Check search failed.") from exc

    hits: list[FactCheckHit] = []
    for claim in payload.get("claims", []):
        claim_text = str(claim.get("text") or "").strip()
        if not claim_text:
            continue
        score = claim_match_score(context, claim_text)
        for review in claim.get("claimReview", []) or []:
            review_url = str(review.get("url") or "").strip()
            if not review_url:
                continue
            publisher_data = review.get("publisher") or {}
            rating = review.get("textualRating")
            hits.append(
                FactCheckHit(
                    claim_text=claim_text,
                    review_title=str(review.get("title") or claim_text).strip(),
                    review_url=review_url,
                    publisher=str(publisher_data.get("name") or publisher_data.get("site") or "").strip() or None,
                    rating=str(rating).strip() if rating is not None else None,
                    review_date=str(review.get("reviewDate") or "").strip() or None,
                    normalized_verdict=normalize_rating(str(rating) if rating is not None else None),
                    match_score=score,
                )
            )

    hits.sort(key=lambda item: item.match_score, reverse=True)
    return hits


def consensus_verdict(hits: list[FactCheckHit], threshold: float = 0.58) -> tuple[Verdict, float, list[FactCheckHit], bool]:
    matched = [hit for hit in hits if hit.match_score >= threshold]
    rated = [hit for hit in matched if hit.normalized_verdict is not None]
    if not rated:
        return Verdict.UNVERIFIED, 0.0, matched, False

    verdicts = {hit.normalized_verdict for hit in rated}
    if len(verdicts) != 1:
        return Verdict.UNVERIFIED, 0.0, matched, True

    verdict = next(iter(verdicts))
    average_match = sum(hit.match_score for hit in rated) / len(rated)
    confidence = min(0.95, 0.62 + 0.28 * average_match + 0.03 * min(len(rated), 3))
    return verdict, round(confidence, 3), matched, False
