import socket

import pytest

from app.models import ExtractionStatus
from app.services.url_extractor import (
    UrlSafetyError,
    assess_social_html,
    normalize_url,
    parse_html,
    platform_for_url,
    validate_public_url,
)


def test_normalize_url_strips_fragment() -> None:
    assert normalize_url("https://Example.com/path?q=1#section") == "https://example.com/path?q=1"


def test_non_http_scheme_is_rejected() -> None:
    with pytest.raises(UrlSafetyError):
        normalize_url("file:///etc/passwd")


def test_private_literal_ip_is_rejected() -> None:
    with pytest.raises(UrlSafetyError):
        validate_public_url("http://127.0.0.1/test")


def test_private_ipv6_literal_is_rejected() -> None:
    with pytest.raises(UrlSafetyError):
        validate_public_url("http://[::1]/test")


def test_hostname_resolving_private_ip_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))])
    with pytest.raises(UrlSafetyError):
        validate_public_url("https://example.com/")


def test_social_domain_matching_does_not_accept_lookalikes() -> None:
    assert platform_for_url("https://www.instagram.com/p/123") == "instagram"
    assert platform_for_url("https://evilinstagram.com/p/123") is None


def test_parse_html_removes_scripts() -> None:
    title, text = parse_html("<html><head><title>Claim page</title><script>steal()</script></head><body><h1>Hello</h1><p>World</p></body></html>")
    assert title == "Claim page"
    assert "Hello World" in text
    assert "steal" not in text


def test_generic_facebook_shell_is_not_treated_as_post_access() -> None:
    html = """
    <html><head><title>Facebook</title></head>
    <body><main>Facebook</main></body></html>
    """
    result = assess_social_html("facebook", html)
    assert result.status == ExtractionStatus.PLATFORM_ONLY
    assert result.title is None
    assert result.text == ""
    assert "could not confirm access" in result.warning


def test_social_login_wall_is_blocked() -> None:
    html = """
    <html><head><title>Facebook</title></head>
    <body>Log in to Facebook to continue</body></html>
    """
    result = assess_social_html("facebook", html)
    assert result.status == ExtractionStatus.BLOCKED
    assert result.text == ""


def test_public_social_description_is_partial_not_full_access() -> None:
    html = """
    <html><head>
      <title>Facebook</title>
      <meta property="og:description" content="A public post claims the city will close all schools tomorrow because of flooding.">
    </head><body>Facebook</body></html>
    """
    result = assess_social_html("facebook", html)
    assert result.status == ExtractionStatus.PARTIAL
    assert result.title is None
    assert "close all schools" in result.text
