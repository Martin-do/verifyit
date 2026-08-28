from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import google.auth
from google.auth.credentials import Credentials
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.auth.transport.requests import Request as GoogleAuthRequest

from app.services.factcheck import FactCheckHit, FactCheckProviderError, search_fact_checks


FACTCHECK_SCOPE = "https://www.googleapis.com/auth/factchecktools"


class EvidenceProviderError(RuntimeError):
    """Raised when a configured evidence provider cannot complete a search."""


class EvidenceProvider(Protocol):
    """Minimal provider contract used by the verification engine."""

    provider_id: str

    def search(self, query: str, context: str) -> list[FactCheckHit]:
        ...


ProviderFactory = Callable[[], EvidenceProvider | None]
_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {}


def register_evidence_provider(provider_id: str, factory: ProviderFactory) -> None:
    """Register a provider factory without changing the verifier."""

    normalized = provider_id.strip().lower()
    if not normalized:
        raise ValueError("provider_id cannot be empty")
    _PROVIDER_FACTORIES[normalized] = factory


@dataclass
class GoogleFactCheckProvider:
    """Bundled adapter for a published fact-check index using OAuth credentials."""

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

    def search(self, query: str, context: str) -> list[FactCheckHit]:
        access_token = self._get_access_token()
        try:
            return search_fact_checks(query, context, access_token)
        except FactCheckProviderError as exc:
            parts: list[str] = []
            if exc.status_code is not None:
                parts.append(f"HTTP {exc.status_code}")
            if exc.detail:
                parts.append(exc.detail)
            safe_detail = " | ".join(parts) or str(exc)
            raise EvidenceProviderError(safe_detail) from None


def _google_factory() -> EvidenceProvider | None:
    # Useful for short-lived local debugging. Production deployments should prefer ADC.
    access_token = os.getenv("VERIFYIT_GOOGLE_ACCESS_TOKEN", "").strip()
    if access_token:
        return GoogleFactCheckProvider(access_token=access_token)

    try:
        credentials, _ = google.auth.default(scopes=[FACTCHECK_SCOPE])
    except DefaultCredentialsError:
        return None

    return GoogleFactCheckProvider(credentials=credentials)


register_evidence_provider("google_factcheck", _google_factory)
register_evidence_provider("google-factcheck", _google_factory)


def get_configured_evidence_provider() -> EvidenceProvider | None:
    """Return the explicitly selected evidence provider when configured.

    ``VERIFYIT_EVIDENCE_PROVIDER`` selects a registered provider. Keeping selection
    explicit avoids silently coupling VerifyIt to any provider found on the host.
    Custom/self-hosted integrations can implement ``EvidenceProvider`` and register
    their own factory.
    """

    provider_id = os.getenv("VERIFYIT_EVIDENCE_PROVIDER", "").strip().lower()
    if not provider_id:
        return None

    factory = _PROVIDER_FACTORIES.get(provider_id)
    return factory() if factory else None
