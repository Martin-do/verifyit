# VerifyIt

VerifyIt is an open-source, evidence-backed verification service for checking claims, links, posts, screenshots, and media before you believe, pay, click, or share.

## Why this exists

Verification is often too much work. Someone sends a social-media link, reel, screenshot, forwarded message, or suspicious offer, and the recipient has to open it, work out the real claim, search for authoritative sources, identify hidden payments or scam signals, and decide whether it is worth trusting.

VerifyIt aims to reduce that to one action.

## Core principles

- **Evidence first:** verdicts must be grounded in retrieved evidence, not model intuition.
- **Transparent uncertainty:** `UNVERIFIED` is a valid result when evidence is insufficient.
- **Source quality matters:** official and primary sources are preferred over secondary summaries.
- **Plain-language output:** users get a concise bottom line before deeper detail.
- **Cross-platform by design:** web, share-sheet, social bots, and messaging integrations reuse the same verification backend.
- **Safety over engagement:** scam, phishing, financial, health, and other high-risk claims surface clear warnings.

## Initial verdicts

- `VERIFIED`
- `MOSTLY_TRUE`
- `MISLEADING`
- `UNVERIFIED`
- `FALSE`
- `SCAM_RISK`

## Current milestone

The first milestone is a runnable API/web shell that establishes the verification contract. Until evidence retrieval is connected, the service deliberately returns `UNVERIFIED` rather than inventing evidence or a verdict.

### Run locally

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment, then install dependencies:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

API documentation is available at `http://127.0.0.1:8000/docs`.

### Run tests

```bash
cd backend
pytest
```

## Repository structure

```text
verifyit/
├── backend/                 # FastAPI verification API
├── web/                     # lightweight MVP web interface
├── docs/                    # architecture and verification methodology
└── .github/workflows/       # continuous integration
```

## Roadmap

1. Evidence-search and source-ranking pipeline
2. URL/content extraction
3. Existing fact-check lookup
4. Scam and hidden-payment analysis
5. Screenshot/image input
6. Video/Reel analysis
7. Browser and Android share integrations
8. X/Instagram/WhatsApp adapters
9. Public verification pages and duplicate-claim detection

## Status

Early development. Do not treat the current MVP shell as a production fact-checking service.
