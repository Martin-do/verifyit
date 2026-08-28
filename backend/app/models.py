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


class VerifyRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    input_type: InputType = InputType.AUTO


class EvidenceItem(BaseModel):
    title: str
    url: str
    source_type: str
    supports_claim: bool | None = None


class VerifyResponse(BaseModel):
    request_id: str
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    claim: str
    summary: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
