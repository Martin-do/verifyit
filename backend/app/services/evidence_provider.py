from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import google.auth
from google.auth.credentials import Credentials
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.auth.transport.requests import Request as GoogleAuthRequest

from app.services.evidence_types import EvidenceHit
from app.services.factcheck import FactCheckProviderError, search_fact_checks
from app.services.web_search import WebSearchProviderError, search_searxng, search_tavily


FACTCHECK_SCOPE = "https://www.googleapis.com/auth/factchecktools"


class EvidenceProviderError(RuntimeError):
    """Raised when a configured evidence provider cannot complete a search."""


class EvidenceProvider(Protocol):
    """Minimal provider-neutral contract used by the verification engine."""

    provider_id: str

    def search(self, query: str, context: str) -> list[EvidenceHit]:
        ...


ProviderFactory = Callable[[], EvidenceProvider | None]
_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {}


def register_evidence_provider(provider_id: str, factory: ProviderFactory) -> None:
    normalized = provider_id.strip().lower()
    if not normalized:
        raise ValueError("provider_id cannot be empty")
    _PROVIDER_FACTORIES[normalized] = factory


def _safe_provider_error(exc: FactCheckProviderError | WebSearchProviderError) -> EvidenceProviderError:
    parts: list[str] = []
    if exc.status_code is not None:
        parts.append(f"HTTP {exc.status_code}")
    if exc.detail:
        parts.append(exc.detail)
    return EvidenceProviderError(" | ".join(parts) or str(exc))


@dataclass
class TavilyProvider:
    api_key: str
    provider_id: str = "tavily"

    def search(self, query: str, context: str) -> list[EvidenceHit]:
        try:
            return search_tavily(query, self.api_key)
        except WebSearchProviderError as exc:
            raise _safe_provider_error(exc) from None


@dataclass
class SearXNGProvider:
    base_url: str
    provider_id: str = "searxng"

    def search(self, query: str, context: str) -> list[EvidenceHit]:
        try:
            return search_searxng(query, self.base_url)
        except WebSearchProviderError as exc:
            raise _safe_provider_error(exc) from None


@dataclass
class GoogleFactCheckProvider:
    """Optional published-fact-check adapter using OAuth credentials."""

    credentials: Credentials | None = None
    access_token: str | None = None
    provider_id: str = "google_factcheck"

    def _get_access_token(self) -> str:
        if self.access_token:
            return self.access_token
        if self.credentials is None:
            raise EvidenceProviderError("OAuth credentials are not configured.")

        if not self.credentials.valid or not self.credentials.token:
            try:
                self.credentials.refresh(GoogleAuthRequest())
            except RefreshError as exc:
                raise EvidenceProviderError(f"OAuth credential refresh failed: {exc.__class__.__name__}") from None

        token = str(self.credentials.token or "").strip()
        if not token:
            raise EvidenceProviderError("OAuth credentials did not provide an access token.")
        return token

    def search(self, query: str, context: str) -> list[EvidenceHit]:
        access_token = self._get_access_token()
        try:
            hits = search_fact_checks(query, context, access_token)
        except FactCheckProviderError as exc:
            raise _safe_provider_error(exc) from None

        return [
            EvidenceHit(
                title=hit.review_title,
                url=hit.review_url,
                source_type="published_fact_check",
                publisher=hit.publisher,
                published_at=hit.review_date,
                rating=hit.rating,
                claim_text=hit.claim_text,
                normalized_verdict=hit.normalized_verdict,
                match_score=hit.match_score,
                provider_score=hit.match_score,
            )
            for hit in hits
        ]


def _tavily_factory() -> EvidenceProvider | None:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    return TavilyProvider(api_key=api_key) if api_key else None


def _searxng_factory() -> EvidenceProvider | None:
    base_url = os.getenv("SEARXNG_BASE_URL", "").strip()
    return SearXNGProvider(base_url=base_url) if base_url else None


def _google_factory() -> EvidenceProvider | None:
    access_token = os.getenv("VERIFYIT_GOOGLE_ACCESS_TOKEN", "").strip()
    if access_token:
        return GoogleFactCheckProvider(access_token=access_token)

    try:
        credentials, _ = google.auth.default(scopes=[FACTCHECK_SCOPE])
    except DefaultCredentialsError:
        return None
    return GoogleFactCheckProvider(credentials=credentials)


register_evidence_provider("tavily", _tavily_factory)
register_evidence_provider("searxng", _searxng_factory)
register_evidence_provider("google_factcheck", _google_factory)
register_evidence_provider("google-factcheck", _google_factory)


def get_configured_evidence_provider() -> EvidenceProvider | None:
    """Return the explicitly selected evidence provider when configured."""

    provider_id = os.getenv("VERIFYIT_EVIDENCE_PROVIDER", "").strip().lower()
    if not provider_id:
        return None

    factory = _PROVIDER_FACTORIES.get(provider_id)
    return factory() if factory else None
