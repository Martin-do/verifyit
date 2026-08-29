from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.services.evidence_types import EvidenceHit


FACT_CHECK_DOMAINS = {
    "africacheck.org",
    "dubawa.org",
    "factcheckhub.com",
    "politifact.com",
    "snopes.com",
}

ESTABLISHED_NEWS_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "afp.com",
}

INSTITUTION_DOMAINS = {
    "who.int",
    "un.org",
    "worldbank.org",
    "imf.org",
}

SOCIAL_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "youtube.com",
    "youtu.be",
}

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from", "has", "have",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "were", "will", "with",
}


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").lower().rstrip(".")


def _matches_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def classify_source(url: str) -> tuple[str, float]:
    """Return a coarse source class and authority prior.

    This score is only a ranking heuristic. It is never evidence that a claim is true.
    """

    host = _host(url)
    if not host:
        return "unknown source", 0.25

    if any(_matches_domain(host, domain) for domain in SOCIAL_DOMAINS):
        return "social platform", 0.20

    if host.endswith(".gov") or host.endswith(".gov.ng") or host.endswith(".go.ke") or host.endswith(".gov.za") or host.endswith(".gov.gh") or host == "gov.uk" or host.endswith(".gov.uk") or host == "europa.eu" or host.endswith(".europa.eu"):
        return "official government source", 0.97

    if any(_matches_domain(host, domain) for domain in INSTITUTION_DOMAINS):
        return "official institution", 0.92

    if host.endswith(".edu") or host.endswith(".edu.ng") or host.endswith(".ac.uk") or host.endswith(".edu.au"):
        return "academic source", 0.84

    if any(_matches_domain(host, domain) for domain in FACT_CHECK_DOMAINS):
        return "recognized fact-checker", 0.88

    if any(_matches_domain(host, domain) for domain in ESTABLISHED_NEWS_DOMAINS):
        return "established news source", 0.79

    return "general web source", 0.50


def _tokens(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", value.lower())
    return {word for word in words if len(word) > 1 and word not in STOP_WORDS}


def lexical_relevance(query: str, title: str, snippet: str | None) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    evidence_tokens = _tokens(f"{title} {snippet or ''}")
    overlap = len(query_tokens & evidence_tokens)
    return round(min(1.0, overlap / len(query_tokens)), 4)


def freshness_score(value: str | None, *, now: datetime | None = None) -> float:
    if not value:
        return 0.50

    candidate = value.strip().replace("Z", "+00:00")
    try:
        published = datetime.fromisoformat(candidate)
    except ValueError:
        return 0.50

    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    age_days = max(0, (current - published.astimezone(timezone.utc)).days)
    if age_days <= 7:
        return 1.0
    if age_days <= 31:
        return 0.92
    if age_days <= 365:
        return 0.78
    if age_days <= 365 * 3:
        return 0.62
    return 0.45


def rank_evidence(hits: list[EvidenceHit], query: str) -> list[EvidenceHit]:
    ranked: list[EvidenceHit] = []
    for hit in hits:
        label, authority = classify_source(hit.url)
        lexical = lexical_relevance(query, hit.title, hit.snippet)
        provider = max(0.0, min(1.0, hit.provider_score or 0.0))
        match = max(0.0, min(1.0, hit.match_score or 0.0))
        relevance = max(lexical, provider, match)
        freshness = freshness_score(hit.published_at)

        # Authority and relevance dominate. Freshness is intentionally a small factor;
        # an old primary source can still be more useful than a new low-quality repost.
        quality = round(0.48 * authority + 0.47 * relevance + 0.05 * freshness, 4)
        ranked.append(
            replace(
                hit,
                source_label=label,
                authority_score=round(authority, 4),
                relevance_score=round(relevance, 4),
                freshness_score=round(freshness, 4),
                quality_score=quality,
            )
        )

    ranked.sort(key=lambda item: (item.quality_score or 0.0, item.relevance_score or 0.0), reverse=True)
    return ranked
