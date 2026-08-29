import httpx
import pytest

from app.services.web_search import WebSearchProviderError, search_searxng, search_tavily


def test_tavily_parses_rankable_results(monkeypatch) -> None:
    request = httpx.Request("POST", "https://api.tavily.com/search")
    response = httpx.Response(
        200,
        request=request,
        json={
            "results": [
                {
                    "title": "Central Bank announcement",
                    "url": "https://www.cbn.gov.ng/example",
                    "content": "Official announcement about the policy.",
                    "score": 0.91,
                }
            ]
        },
    )
    captured: dict[str, object] = {}

    def fake_post(*args, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return response

    monkeypatch.setattr(httpx, "post", fake_post)
    hits = search_tavily("policy announcement", "tvly-secret")
    assert len(hits) == 1
    assert hits[0].source_type == "web_search"
    assert hits[0].provider_score == 0.91
    assert captured["headers"]["Authorization"] == "Bearer tvly-secret"


def test_tavily_error_does_not_include_api_key(monkeypatch) -> None:
    request = httpx.Request("POST", "https://api.tavily.com/search")
    response = httpx.Response(401, request=request, json={"detail": "Unauthorized"})
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)

    with pytest.raises(WebSearchProviderError) as caught:
        search_tavily("claim", "tvly-super-secret")

    assert caught.value.status_code == 401
    assert "tvly-super-secret" not in str(caught.value)
    assert "tvly-super-secret" not in (caught.value.detail or "")


def test_searxng_parses_json_results(monkeypatch) -> None:
    request = httpx.Request("GET", "https://search.example/search")
    response = httpx.Response(
        200,
        request=request,
        json={
            "results": [
                {
                    "title": "WHO guidance",
                    "url": "https://www.who.int/example",
                    "content": "Official health guidance.",
                    "score": 0.8,
                }
            ]
        },
    )
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: response)
    hits = search_searxng("health guidance", "https://search.example")
    assert len(hits) == 1
    assert hits[0].url == "https://www.who.int/example"


def test_searxng_requires_http_url() -> None:
    with pytest.raises(WebSearchProviderError):
        search_searxng("claim", "search.example")
