from __future__ import annotations

from urllib.parse import urljoin

import httpx

from app.services.evidence_types import EvidenceHit


class WebSearchProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, detail: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


def _safe_error_detail(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None

    if isinstance(payload, dict):
        for key in ("detail", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:500]
            if isinstance(value, dict):
                message = value.get("message") or value.get("detail")
                if isinstance(message, str) and message.strip():
                    return message.strip()[:500]
    return None


def search_tavily(query: str, api_key: str, *, max_results: int = 8) -> list[EvidenceHit]:
    payload = {
        "query": " ".join(query.split())[:500],
        "search_depth": "basic",
        "max_results": max(1, min(max_results, 10)),
        "include_answer": False,
        "include_raw_content": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post("https://api.tavily.com/search", json=payload, headers=headers, timeout=12.0)
    except httpx.TimeoutException:
        raise WebSearchProviderError("Web search request timed out.", detail="request timed out") from None
    except httpx.RequestError as exc:
        raise WebSearchProviderError("Web search network request failed.", detail=exc.__class__.__name__) from None

    if response.status_code >= 400:
        raise WebSearchProviderError(
            "Web search provider returned an HTTP error.",
            status_code=response.status_code,
            detail=_safe_error_detail(response),
        )

    try:
        data = response.json()
    except ValueError:
        raise WebSearchProviderError("Web search provider returned invalid JSON.", status_code=response.status_code) from None

    hits: list[EvidenceHit] = []
    for item in data.get("results", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not url or not title:
            continue
        score = item.get("score")
        try:
            provider_score = float(score) if score is not None else None
        except (TypeError, ValueError):
            provider_score = None
        hits.append(
            EvidenceHit(
                title=title[:500],
                url=url,
                source_type="web_search",
                snippet=str(item.get("content") or "").strip()[:2000] or None,
                published_at=str(item.get("published_date") or item.get("publishedDate") or "").strip() or None,
                provider_score=provider_score,
            )
        )
    return hits


def search_searxng(query: str, base_url: str, *, max_results: int = 8) -> list[EvidenceHit]:
    base = base_url.strip().rstrip("/") + "/"
    if not base.startswith(("http://", "https://")):
        raise WebSearchProviderError("SearXNG base URL must use http:// or https://.")

    endpoint = urljoin(base, "search")
    params = {
        "q": " ".join(query.split())[:500],
        "format": "json",
        "safesearch": 1,
    }

    try:
        response = httpx.get(endpoint, params=params, timeout=12.0, follow_redirects=False)
    except httpx.TimeoutException:
        raise WebSearchProviderError("Web search request timed out.", detail="request timed out") from None
    except httpx.RequestError as exc:
        raise WebSearchProviderError("Web search network request failed.", detail=exc.__class__.__name__) from None

    if response.status_code >= 400:
        raise WebSearchProviderError(
            "Web search provider returned an HTTP error.",
            status_code=response.status_code,
            detail=_safe_error_detail(response),
        )

    try:
        data = response.json()
    except ValueError:
        raise WebSearchProviderError("Web search provider returned invalid JSON.", status_code=response.status_code) from None

    hits: list[EvidenceHit] = []
    results = data.get("results", []) if isinstance(data, dict) else []
    for item in results[: max(1, min(max_results, 20))]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not url or not title:
            continue
        score = item.get("score")
        try:
            provider_score = min(1.0, max(0.0, float(score))) if score is not None else None
        except (TypeError, ValueError):
            provider_score = None
        hits.append(
            EvidenceHit(
                title=title[:500],
                url=url,
                source_type="web_search",
                snippet=str(item.get("content") or "").strip()[:2000] or None,
                published_at=str(item.get("publishedDate") or item.get("published_date") or "").strip() or None,
                provider_score=provider_score,
            )
        )
    return hits
