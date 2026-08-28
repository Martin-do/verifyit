from uuid import uuid4

from app.models import VerifyRequest, VerifyResponse, Verdict


NOT_CONNECTED_WARNING = (
    "Evidence retrieval is not connected yet. No factual verdict has been inferred "
    "from the language model or from the submitted content alone."
)


def verify(request: VerifyRequest) -> VerifyResponse:
    """Return a safe placeholder until the evidence pipeline is implemented.

    This is deliberately conservative. The first development milestone establishes
    the API contract without pretending that an ungrounded model response is a
    fact-check.
    """

    content = request.content.strip()

    return VerifyResponse(
        request_id=str(uuid4()),
        verdict=Verdict.UNVERIFIED,
        confidence=0.0,
        claim=content,
        summary=(
            "VerifyIt received the content, but the evidence-search pipeline is not "
            "connected yet. The claim has therefore not been verified."
        ),
        evidence=[],
        warnings=[NOT_CONNECTED_WARNING],
    )
