from __future__ import annotations

from uuid import uuid4

from app.models import EvidenceItem, ExtractionStatus, InputType, VerifyRequest, VerifyResponse, Verdict
from app.services.evidence_provider import EvidenceProviderError, get_configured_evidence_provider
from app.services.factcheck import consensus_verdict
from app.services.url_extractor import fetch_url, looks_like_url


def _detected_type(request: VerifyRequest) -> InputType:
    if request.input_type != InputType.AUTO:
        return request.input_type
    return InputType.URL if looks_like_url(request.content) else InputType.TEXT


def _evidence_from_hits(hits) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.review_url in seen:
            continue
        seen.add(hit.review_url)
        evidence.append(
            EvidenceItem(
                title=hit.review_title,
                url=hit.review_url,
                source_type="published_fact_check",
                publisher=hit.publisher,
                rating=hit.rating,
                review_date=hit.review_date,
                claim_text=hit.claim_text,
                match_score=hit.match_score,
            )
        )
        if len(evidence) >= 6:
            break
    return evidence


def _summary_for(verdict: Verdict, evidence_count: int) -> str:
    if verdict == Verdict.UNVERIFIED:
        if evidence_count:
            return "VerifyIt found related published evidence, but it was not strong or consistent enough to assign a factual verdict safely."
        return "VerifyIt could not find sufficient matching evidence to assign a factual verdict."
    return f"VerifyIt found matching published evidence and the matched reviews support the verdict {verdict.value}."


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
    except EvidenceProviderError:
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

    verdict, confidence, matched_hits, conflicting = consensus_verdict(hits)
    evidence_hits = matched_hits if matched_hits else [hit for hit in hits if hit.match_score >= 0.35]
    evidence = _evidence_from_hits(evidence_hits)

    if conflicting:
        warnings.append("Matching evidence reviews produced conflicting normalized ratings, so VerifyIt kept the verdict UNVERIFIED.")
    elif hits and not matched_hits:
        warnings.append("Published evidence was found, but its claims did not match the submitted content closely enough for a verdict.")
    elif not hits:
        warnings.append("No published evidence matched the evidence query.")

    return VerifyResponse(
        request_id=str(uuid4()),
        verdict=verdict,
        confidence=confidence,
        claim=claim,
        summary=_summary_for(verdict, len(evidence)),
        evidence=evidence,
        warnings=warnings,
        detected_input_type=detected,
        source_url=source_url,
        extraction_status=extraction_status,
        extracted_title=extracted_title,
    )
