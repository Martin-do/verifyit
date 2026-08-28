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

VerifyIt 0.2 can inspect accessible public HTTP/HTTPS pages and optionally search published ClaimReview fact checks through Google's Fact Check Tools API. It still fails safe: inaccessible content, weak matches, conflicting ratings, or missing evidence remain `UNVERIFIED`.

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

### Enable published fact-check search

Google's Fact Check Tools API requires an API key. Enable the **Fact Check Tools API** in a Google Cloud project and create an API key, then copy the repository example file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set:

```text
GOOGLE_FACT_CHECK_API_KEY=your_key_here
```

The `.env` file is ignored by Git and must never be committed. Restart the local server after changing it.

Without this key, URL extraction still works, but VerifyIt deliberately keeps factual verdicts `UNVERIFIED` because no external fact-check evidence provider is configured.

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

## Evidence behavior

For URLs, VerifyIt applies application-level SSRF defenses, follows only re-validated redirects, limits download size/time, extracts readable HTML/text, and reports login walls or unsupported media instead of inventing the hidden content.

For published fact checks, a search result is not automatically treated as truth. The reviewed claim must substantially match the submitted/extracted context, and matched normalized ratings must agree before a non-`UNVERIFIED` verdict is produced.

See `docs/evidence-pipeline.md` for details and limitations.

## Roadmap

1. **In progress:** evidence providers and source ranking beyond existing fact checks
2. **Implemented (MVP):** safe URL/content extraction
3. **Implemented (MVP):** existing fact-check lookup
4. Scam and hidden-payment analysis
5. Screenshot/image input
6. Video/Reel analysis
7. Browser and Android share integrations
8. X/Instagram/WhatsApp adapters
9. Public verification pages and duplicate-claim detection

## Status

Early development. VerifyIt is not yet a production fact-checking service, and a verdict should always remain inspectable through its evidence.
