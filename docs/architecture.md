# VerifyIt Architecture

## Design goal

One verification engine, many entry points.

```text
Web / Android Share / Browser Extension / X / Instagram / WhatsApp
                              |
                              v
                         VerifyIt API
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
   Content extraction    Claim extraction     Risk signals
          |                   |                   |
          +-------------------+-------------------+
                              |
                              v
                       Evidence retrieval
                              |
                              v
                        Source ranking
                              |
                              v
                      Evidence synthesis
                              |
                              v
                 Verdict + citations + warnings
```

## Architectural rule

Platform adapters must not contain verification logic. They translate a platform-specific event into the common VerifyIt request schema and render the common response.

## MVP boundary

The bootstrap release implements only the API contract and a minimal web surface. Evidence retrieval and model-assisted analysis are deliberately absent until their contracts and evaluation criteria are defined.

## Planned backend modules

- `content_extraction`: obtains accessible text/metadata from submitted URLs and media.
- `claim_extraction`: identifies checkable factual claims without deciding truth.
- `evidence_search`: gathers candidate evidence from authoritative web and fact-check sources.
- `source_ranking`: ranks sources by authority, relevance, freshness, and directness.
- `risk_analysis`: detects scam, phishing, hidden-payment, urgency, impersonation, and other risk signals.
- `verification`: compares claims with evidence and assigns a constrained verdict.
- `response_generation`: produces a short bottom line plus inspectable evidence.

## Trust boundary

A language model may assist with extraction, search planning, comparison, and explanation. It must not be treated as the evidence source. A verdict must be traceable to retrieved evidence, or the result remains `UNVERIFIED`.
