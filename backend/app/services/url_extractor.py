from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from app.models import ExtractionStatus


MAX_RESPONSE_BYTES = 1_500_000
MAX_REDIRECTS = 5
REQUEST_TIMEOUT_SECONDS = 8.0
USER_AGENT = "VerifyIt/0.2 (+https://github.com/Martin-do/verifyit)"
SOCIAL_PLATFORMS = {"facebook", "instagram", "x", "tiktok"}


class UrlSafetyError(ValueError):
    pass


@dataclass
class SocialPageAssessment:
    status: ExtractionStatus
    title: str | None = None
    text: str = ""
    warning: str = ""


@dataclass
class ExtractedPage:
    requested_url: str
    final_url: str | None = None
    status: ExtractionStatus = ExtractionStatus.FETCH_FAILED
    title: str | None = None
    text: str = ""
    platform: str | None = None
    content_type: str | None = None
    warnings: list[str] = field(default_factory=list)


def looks_like_url(value: str) -> bool:
    candidate = value.strip()
    if candidate.startswith(("http://", "https://")):
        parsed = urlparse(candidate)
        return bool(parsed.netloc)
    return False


def normalize_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UrlSafetyError("Only http:// and https:// URLs are supported.")
    if not parsed.hostname:
        raise UrlSafetyError("The URL does not contain a valid hostname.")
    if parsed.username or parsed.password:
        raise UrlSafetyError("URLs containing embedded credentials are not allowed.")

    host = parsed.hostname.lower().rstrip(".")
    try:
        port = parsed.port
    except ValueError as exc:
        raise UrlSafetyError("The URL contains an invalid port.") from exc

    if port is not None and port not in {80, 443}:
        raise UrlSafetyError("Only standard HTTP and HTTPS ports are allowed.")

    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host
    if port and not ((parsed.scheme.lower() == "http" and port == 80) or (parsed.scheme.lower() == "https" and port == 443)):
        netloc = f"{display_host}:{port}"

    return urlunparse((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.params, parsed.query, ""))


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_url(value: str) -> str:
    normalized = normalize_url(value)
    hostname = urlparse(normalized).hostname
    assert hostname is not None

    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise UrlSafetyError("Local network hostnames are not allowed.")

    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if not _is_public_address(str(literal_ip)):
            raise UrlSafetyError("Private or non-public network addresses are not allowed.")
        return normalized

    try:
        resolved = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlSafetyError("The hostname could not be resolved.") from exc

    addresses = {item[4][0] for item in resolved}
    if not addresses:
        raise UrlSafetyError("The hostname did not resolve to an address.")
    if any(not _is_public_address(address) for address in addresses):
        raise UrlSafetyError("The hostname resolves to a private or non-public network address.")

    return normalized


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def platform_for_url(value: str) -> str | None:
    host = (urlparse(value).hostname or "").lower()
    if _host_matches(host, "facebook.com"):
        return "facebook"
    if _host_matches(host, "instagram.com"):
        return "instagram"
    if _host_matches(host, "x.com") or _host_matches(host, "twitter.com"):
        return "x"
    if _host_matches(host, "tiktok.com"):
        return "tiktok"
    return None


def parse_html(html: str) -> tuple[str | None, str]:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript", "template", "svg"]):
        node.decompose()

    title = None
    if soup.title and soup.title.string:
        title = " ".join(soup.title.string.split())[:500]

    text = " ".join(soup.get_text(" ", strip=True).split())
    return title, text[:20_000]


def extract_social_description(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates = (
        ("property", "og:description"),
        ("name", "description"),
        ("name", "twitter:description"),
    )
    for attr, value in candidates:
        tag = soup.find("meta", attrs={attr: value})
        if tag and tag.get("content"):
            description = " ".join(str(tag.get("content")).split())
            if description:
                return description[:5000]
    return None


def _looks_like_login_wall(platform: str | None, title: str | None, text: str) -> bool:
    if platform not in SOCIAL_PLATFORMS:
        return False
    sample = f"{title or ''} {text[:2500]}".lower()
    markers = (
        "log in to facebook",
        "login to facebook",
        "log into facebook",
        "log in to instagram",
        "login to instagram",
        "sign up for instagram",
        "log in to x",
        "sign in to x",
        "log in to tiktok",
        "sign up for tiktok",
    )
    return any(marker in sample for marker in markers)


def _generic_social_title(platform: str, title: str | None) -> bool:
    if not title:
        return True
    normalized = " ".join(title.lower().split()).strip(" -|·")
    generic = {
        "facebook": {"facebook", "facebook – log in or sign up", "facebook - log in or sign up"},
        "instagram": {"instagram", "instagram • photos and videos"},
        "x": {"x", "twitter", "x / twitter"},
        "tiktok": {"tiktok", "tiktok - make your day"},
    }
    return normalized in generic.get(platform, set())


def _meaningful_social_description(platform: str, description: str | None) -> bool:
    if not description or len(description.strip()) < 24:
        return False
    sample = description.lower()
    generic_markers = (
        "log in to facebook",
        "create an account or log into facebook",
        "facebook helps you connect",
        "log in to instagram",
        "sign up to see photos",
        "see instagram photos",
        "log in to x",
        "sign up for x",
        "log in to tiktok",
        "join tiktok",
    )
    if any(marker in sample for marker in generic_markers):
        return False
    return sample.strip(" .-|·") != platform


def assess_social_html(platform: str, html: str, title: str | None = None, text: str | None = None) -> SocialPageAssessment:
    """Classify a social HTML response without assuming HTTP success means post access."""

    if title is None or text is None:
        parsed_title, parsed_text = parse_html(html)
        title = parsed_title if title is None else title
        text = parsed_text if text is None else text

    safe_title = None if _generic_social_title(platform, title) else title
    if _looks_like_login_wall(platform, title, text):
        return SocialPageAssessment(
            status=ExtractionStatus.BLOCKED,
            title=safe_title,
            warning=(
                "The social platform exposed a login/interstitial page rather than the actual post. "
                "VerifyIt will not infer the hidden content. Upload a screenshot/video or paste the post text to continue."
            ),
        )

    description = extract_social_description(html)
    if _meaningful_social_description(platform, description):
        return SocialPageAssessment(
            status=ExtractionStatus.PARTIAL,
            title=safe_title,
            text=description or "",
            warning=(
                "Only public text metadata from the social post was accessible. VerifyIt could not confirm access to all post media or context, "
                "so only that accessible text may be used."
            ),
        )

    return SocialPageAssessment(
        status=ExtractionStatus.PLATFORM_ONLY,
        title=safe_title,
        warning=(
            "The platform responded, but VerifyIt could not confirm access to the actual post content. "
            "Nothing from the unseen post was used. Upload a screenshot/video or paste the post text to continue."
        ),
    )


def fetch_url(value: str) -> ExtractedPage:
    requested = value.strip()
    try:
        current = validate_public_url(requested)
    except UrlSafetyError as exc:
        return ExtractedPage(requested_url=requested, status=ExtractionStatus.REJECTED, warnings=[str(exc)])

    platform = platform_for_url(current)
    client = httpx.Client(
        follow_redirects=False,
        timeout=REQUEST_TIMEOUT_SECONDS,
        trust_env=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9,*/*;q=0.2"},
    )

    try:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                with client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            return ExtractedPage(requested_url=requested, final_url=current, platform=platform, status=ExtractionStatus.FETCH_FAILED, warnings=["The URL returned a redirect without a destination."])
                        current = validate_public_url(urljoin(current, location))
                        platform = platform_for_url(current) or platform
                        continue

                    if response.status_code in {401, 403}:
                        return ExtractedPage(requested_url=requested, final_url=current, platform=platform, status=ExtractionStatus.BLOCKED, warnings=[f"The source returned HTTP {response.status_code}; its contents could not be inspected."])

                    if response.status_code >= 400:
                        return ExtractedPage(requested_url=requested, final_url=current, platform=platform, status=ExtractionStatus.FETCH_FAILED, warnings=[f"The source returned HTTP {response.status_code}."])

                    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                    if content_type and content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
                        return ExtractedPage(
                            requested_url=requested,
                            final_url=current,
                            platform=platform,
                            content_type=content_type,
                            status=ExtractionStatus.PARTIAL,
                            warnings=[f"The URL points to {content_type or 'non-text content'}. Direct media analysis is not implemented yet."],
                        )

                    data = bytearray()
                    truncated = False
                    for chunk in response.iter_bytes():
                        if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                            remaining = MAX_RESPONSE_BYTES - len(data)
                            if remaining > 0:
                                data.extend(chunk[:remaining])
                            truncated = True
                            break
                        data.extend(chunk)

                    encoding = response.encoding or "utf-8"
                    raw_text = bytes(data).decode(encoding, errors="replace")
                    if content_type == "text/plain":
                        title = None
                        text = " ".join(raw_text.split())[:20_000]
                    else:
                        title, text = parse_html(raw_text)

                    if platform in SOCIAL_PLATFORMS:
                        assessment = assess_social_html(platform, raw_text, title=title, text=text)
                        return ExtractedPage(
                            requested_url=requested,
                            final_url=current,
                            platform=platform,
                            content_type=content_type,
                            title=assessment.title,
                            text=assessment.text,
                            status=assessment.status,
                            warnings=[assessment.warning] if assessment.warning else [],
                        )

                    warnings: list[str] = []
                    status = ExtractionStatus.ACCESSED
                    if truncated:
                        status = ExtractionStatus.PARTIAL
                        warnings.append("The page was larger than the extraction limit, so only the first portion was inspected.")

                    return ExtractedPage(
                        requested_url=requested,
                        final_url=current,
                        platform=platform,
                        content_type=content_type,
                        title=title,
                        text=text,
                        status=status,
                        warnings=warnings,
                    )
            except UrlSafetyError as exc:
                return ExtractedPage(requested_url=requested, final_url=current, platform=platform, status=ExtractionStatus.REJECTED, warnings=[f"A redirect was rejected for safety: {exc}"])
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                return ExtractedPage(requested_url=requested, final_url=current, platform=platform, status=ExtractionStatus.FETCH_FAILED, warnings=[f"The source could not be fetched: {exc.__class__.__name__}."])

        return ExtractedPage(requested_url=requested, final_url=current, platform=platform, status=ExtractionStatus.FETCH_FAILED, warnings=["Too many redirects were encountered."])
    finally:
        client.close()
