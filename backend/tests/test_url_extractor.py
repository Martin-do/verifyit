import socket

import pytest

from app.models import ExtractionStatus
from app.services.url_extractor import UrlSafetyError, normalize_url, parse_html, validate_public_url


def test_normalize_url_strips_fragment() -> None:
    assert normalize_url("https://Example.com/path?q=1#section") == "https://example.com/path?q=1"


def test_non_http_scheme_is_rejected() -> None:
    with pytest.raises(UrlSafetyError):
        normalize_url("file:///etc/passwd")


def test_private_literal_ip_is_rejected() -> None:
    with pytest.raises(UrlSafetyError):
        validate_public_url("http://127.0.0.1/test")


def test_hostname_resolving_private_ip_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))],
    )
    with pytest.raises(UrlSafetyError):
        validate_public_url("https://example.com/")


def test_parse_html_removes_scripts() -> None:
    title, text = parse_html("<html><head><title>Claim page</title><script>steal()</script></head><body><h1>Hello</h1><p>World</p></body></html>")
    assert title == "Claim page"
    assert "Hello World" in text
    assert "steal" not in text
