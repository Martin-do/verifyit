from enum import Enum

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    VERIFIED = "VERIFIED"
    MOSTLY_TRUE = "MOSTLY_TRUE"
    MISLEADING = "MISLEADING"
    UNVERIFIED = "UNVERIFIED"
    FALSE = "FALSE"
    SCAM_RISK = "SCAM_RISK"


class InputType(str, Enum):
    AUTO = "auto"
    TEXT = "text"
    URL = "url"


class ExtractionStatus(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    ACCESSED = "accessed"
    PARTIAL = "partial"
    PLATFORM_ONLY = "platform_only"
    BLOCKED = "blocked"
    FETCH_FAILED = "fetch_failed"
    REJECTED = "rejected"


class VerifyRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    input_type: InputType = InputType.AUTO


class EvidenceItem(BaseModel):
    title: str
    url: str
    source_type: str
    supports_claim: bool | None = None
    publisher: str | None = None
    snippet: str | None = None
    rating: str | None = None
    review_date: str | None = None
    claim_text: str | None = None
    source_label: str | None = None
    match_score: float | None = Field(default=None, ge=0.0, le=1.0)
    authority_score: float | None = Field(default=None, ge=0.0, le=1.0)
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)


class VerifyResponse(BaseModel):
    request_id: str
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    claim: str
    summary: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    detected_input_type: InputType = InputType.TEXT
    source_url: str | None = None
    extraction_status: ExtractionStatus = ExtractionStatus.NOT_APPLICABLE
    extracted_title: str | None = None
