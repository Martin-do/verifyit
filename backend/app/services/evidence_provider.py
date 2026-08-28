from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.services.factcheck import FactCheckHit, FactCheckProviderError, search_fact_checks


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
    """Bundled adapter for a published fact-check index."""

    api_key: str
    provider_id: str = "google_factcheck"

    def search(self, query: str, context: str) -> list[FactCheckHit]:
        try:
            return search_fact_checks(query, context, self.api_key)
        except FactCheckProviderError as exc:
            raise EvidenceProviderError("The configured evidence provider failed.") from exc


def _google_factory() -> EvidenceProvider | None:
    api_key = os.getenv("GOOGLE_FACT_CHECK_API_KEY", "").strip()
    if not api_key:
        return None
    return GoogleFactCheckProvider(api_key=api_key)


register_evidence_provider("google_factcheck", _google_factory)
register_evidence_provider("google-factcheck", _google_factory)


def get_configured_evidence_provider() -> EvidenceProvider | None:
    """Return the selected evidence provider when its configuration is available.

    ``VERIFYIT_EVIDENCE_PROVIDER`` selects a registered provider. Custom/self-hosted
    integrations can implement ``EvidenceProvider`` and register their own factory.
    During the MVP, the bundled adapter is auto-detected when its key is present.
    """

    provider_id = os.getenv("VERIFYIT_EVIDENCE_PROVIDER", "").strip().lower()
    if provider_id:
        factory = _PROVIDER_FACTORIES.get(provider_id)
        return factory() if factory else None

    return _google_factory()
