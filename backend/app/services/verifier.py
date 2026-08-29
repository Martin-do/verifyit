from __future__ import annotations

import logging
from uuid import uuid4

from app.models import EvidenceItem, ExtractionStatus, InputType, VerifyRequest, VerifyResponse, Verdict
from app.services.evidence_provider import EvidenceProviderError, get_configured_evidence_provider
from app.services.evidence_types import EvidenceHit
from app.services.source_ranker import rank_evidence
from app.services.url_extractor import fetch_url, looks_like_url


logger = logging.getLogger("verifyit.evidence")


def _detected_type(request: VerifyRequest) -> InputType:
    if request.input_type != InputType.AUTO:
        return request.input_type
    return InputType.URL if looks_like_url(request.content) else InputType.TEXT


def _evidence_from_hits(hits: list[EvidenceHit], limit: int = 8) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.url in seen:
            continue
        seen.add(hit.url)
        evidence.append(
            EvidenceItem(
                title=hit.title,
                url=hit.url,
                source_type=hit.source_type,
                publisher=hit.publisher,
                snippet=hit.snippet,
                rating=hit.rating,
                review_date=hit.published_at,
                claim_text=hit.claim_text,
                source_label=hit.source_label,
                match_score=hit.match_score,
                authority_score=hit.authority_score,
                relevance_score=hit.relevance_score,
                quality_score=hit.quality_score,
            )
        )
        if len(evidence) >= limit:
            break
    return evidence


def _factcheck_consensus(hits: list[EvidenceHit], threshold: float = 0.58) -> tuple[Verdict, float, list[EvidenceHit], bool]:
    matched = [hit for hit in hits if (hit.match_score or 0.0) >= threshold]
    rated = [hit for hit in matched if hit.normalized_verdict is not None]
    if not rated:
        return Verdict.UNVERIFIED, 0.0, matched, False

    verdicts = {hit.normalized_verdict for hit in rated}
    if len(verdicts) != 1:
        return Verdict.UNVERIFIED, 0.0, matched, True

    verdict = next(iter(verdicts))
    average_match = sum(hit.match_score or 0.0 for hit in rated) / len(rated)
    confidence = min(0.95, 0.62 + 0.28 * average_match + 0.03 * min(len(rated), 3))
    return verdict, round(confidence, 3), matched, False


def _unavailable_social_response(
    *,
    content: str,
    detected: InputType,
    source_url: str,
    extraction_status: ExtractionStatus,
    extracted_title: str | None,
    warnings: list[str],
) -> VerifyResponse:
    return VerifyResponse(
        request_id=str(uuid4()),
        verdict=Verdict.UNVERIFIED,
        confidence=0.0,
        claim=content,
        summary=(
            "VerifyIt reached the social platform, but could not confirm access to the actual post content. "
            "Nothing from the unseen post was used in the assessment."
        ),
        warnings=warnings,
        detected_input_type=detected,
        source_url=source_url,
        extraction_status=extraction_status,
        extracted_title=extracted_title,
    )


def verify(request: VerifyRequest) -> VerifyResponse:
    content = request.content.strip()
    detected = _detected_type(request)
    warnings: list[str] = []
    source_url: str | None = None
    extracted_title: str | None = None
    extraction_status = ExtractionStatus.NOT_APPLICABLE
    verification_context = content
    search_query = content
    claim = content

    if detected == InputType.URL:
        page = fetch_url(content)
        source_url = page.final_url or content
        extracted_title = page.title
        extraction_status = page.status
        warnings.extend(page.warnings)

        if page.status in {ExtractionStatus.REJECTED, ExtractionStatus.FETCH_FAILED}:
            return VerifyResponse(
                request_id=str(uuid4()),
                verdict=Verdict.UNVERIFIED,
                confidence=0.0,
                claim=content,
                summary="VerifyIt could not safely inspect the submitted URL, so no factual verdict was assigned.",
                warnings=warnings,
                detected_input_type=detected,
                source_url=source_url,
                extraction_status=extraction_status,
                extracted_title=extracted_title,
            )

        if page.status in {ExtractionStatus.BLOCKED, ExtractionStatus.PLATFORM_ONLY}:
            return _unavailable_social_response(
                content=content,
                detected=detected,
                source_url=source_url,
                extraction_status=extraction_status,
                extracted_title=extracted_title,
                warnings=warnings,
            )

        if page.title:
            claim = page.title
        if page.text:
            if not page.title and page.platform:
                claim = page.text[:500]
            verification_context = f"{page.title or ''} {page.text[:12_000]}".strip()
            search_query = f"{page.title or ''} {page.text[:300]}".strip()
        elif page.title:
            verification_context = page.title
            search_query = page.title
        else:
            warnings.append("The URL was reachable, but VerifyIt could not extract enough text to identify its claim.")

    provider = get_configured_evidence_provider()
    if provider is None:
        warnings.append(
            "External evidence search is not configured. VerifyIt inspected the available content but cannot perform independent evidence retrieval yet."
        )
        return VerifyResponse(
            request_id=str(uuid4()),
            verdict=Verdict.UNVERIFIED,
            confidence=0.0,
            claim=claim,
            summary="VerifyIt inspected the input where possible, but no external evidence provider is configured, so it will not guess a verdict.",
            evidence=[],
            warnings=warnings,
            detected_input_type=detected,
            source_url=source_url,
            extraction_status=extraction_status,
            extracted_title=extracted_title,
        )

    if not search_query.strip():
        warnings.append("There was not enough extractable text to search for external evidence.")
        return VerifyResponse(
            request_id=str(uuid4()),
            verdict=Verdict.UNVERIFIED,
            confidence=0.0,
            claim=claim,
            summary="VerifyIt could not form a reliable evidence query from the submitted content.",
            evidence=[],
            warnings=warnings,
            detected_input_type=detected,
            source_url=source_url,
            extraction_status=extraction_status,
            extracted_title=extracted_title,
        )

    try:
        hits = provider.search(search_query, verification_context)
    except EvidenceProviderError as exc:
        logger.warning("Evidence provider '%s' failed: %s", getattr(provider, "provider_id", "unknown"), exc)
        warnings.append("External evidence search is temporarily unavailable. No verdict was inferred without supporting evidence.")
        return VerifyResponse(
            request_id=str(uuid4()),
            verdict=Verdict.UNVERIFIED,
            confidence=0.0,
            claim=claim,
            summary="Evidence retrieval failed, so VerifyIt did not assign a factual verdict.",
            warnings=warnings,
            detected_input_type=detected,
            source_url=source_url,
            extraction_status=extraction_status,
            extracted_title=extracted_title,
        )

    ranked_hits = rank_evidence(hits, search_query)
    factcheck_hits = [hit for hit in ranked_hits if hit.source_type == "published_fact_check"]
    web_hits = [hit for hit in ranked_hits if hit.source_type == "web_search"]

    if factcheck_hits:
        verdict, confidence, matched_hits, conflicting = _factcheck_consensus(factcheck_hits)
        evidence_hits = matched_hits if matched_hits else [hit for hit in factcheck_hits if (hit.match_score or 0.0) >= 0.35]
        evidence = _evidence_from_hits(rank_evidence(evidence_hits, search_query))

        if conflicting:
            warnings.append("Matching evidence reviews produced conflicting normalized ratings, so VerifyIt kept the verdict UNVERIFIED.")
        elif factcheck_hits and not matched_hits:
            warnings.append("Published fact checks were found, but their claims did not match the submitted content closely enough for a verdict.")

        summary = (
            f"VerifyIt found matching published evidence and the matched reviews support the verdict {verdict.value}."
            if verdict != Verdict.UNVERIFIED
            else "VerifyIt found related published evidence, but it was not strong or consistent enough to assign a factual verdict safely."
        )
        return VerifyResponse(
            request_id=str(uuid4()),
            verdict=verdict,
            confidence=confidence,
            claim=claim,
            summary=summary,
            evidence=evidence,
            warnings=warnings,
            detected_input_type=detected,
            source_url=source_url,
            extraction_status=extraction_status,
            extracted_title=extracted_title,
        )

    if web_hits:
        evidence = _evidence_from_hits(web_hits)
        warnings.append(
            "VerifyIt has retrieved and ranked candidate sources, but automated claim-versus-source synthesis is not enabled yet. "
            "Search-result snippets alone are not enough for a factual verdict."
        )
        return VerifyResponse(
            request_id=str(uuid4()),
            verdict=Verdict.UNVERIFIED,
            confidence=0.0,
            claim=claim,
            summary=f"VerifyIt retrieved and ranked {len(evidence)} external sources for inspection without guessing a verdict.",
            evidence=evidence,
            warnings=warnings,
            detected_input_type=detected,
            source_url=source_url,
            extraction_status=extraction_status,
            extracted_title=extracted_title,
        )

    warnings.append("No external evidence matched the evidence query.")
    return VerifyResponse(
        request_id=str(uuid4()),
        verdict=Verdict.UNVERIFIED,
        confidence=0.0,
        claim=claim,
        summary="VerifyIt could not find sufficient matching evidence to assign a factual verdict.",
        evidence=[],
        warnings=warnings,
        detected_input_type=detected,
        source_url=source_url,
        extraction_status=extraction_status,
        extracted_title=extracted_title,
    )
