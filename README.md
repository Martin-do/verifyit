# VerifyIt

VerifyIt is an open-source, evidence-backed verification service for checking claims, links, posts, screenshots, and media before you believe, pay, click, or share.

## Why this exists

Verification is often too much work. Someone sends a social-media link, reel, screenshot, forwarded message, or suspicious offer, and the recipient has to open it, work out the real claim, search for authoritative sources, identify hidden payments or scam signals, and decide whether it is worth trusting.

VerifyIt aims to reduce that to one action.

## Core principles

- **Evidence first:** verdicts must be grounded in retrieved evidence, not model intuition.
- **Transparent uncertainty:** `UNVERIFIED` is a valid result when evidence is insufficient.
- **Source quality matters:** official and primary sources are preferred over secondary summaries.
- **Provider-neutral core:** evidence retrieval is behind a generic provider interface rather than tied to one vendor.
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

VerifyIt 0.3 can inspect accessible public HTTP/HTTPS pages, retrieve general web evidence through a configured provider, and rank candidate sources by authority, relevance, and freshness. Search snippets are **not** treated as sufficient evidence for a factual verdict, so general-search-only checks remain `UNVERIFIED` until full claim-versus-source synthesis is implemented.

Social-media HTML is treated more cautiously than ordinary webpages. A platform returning a generic shell does **not** mean the underlying post was accessed. VerifyIt distinguishes full page access, partial public metadata, platform-only responses, blocked/login-wall content, fetch failures, and rejected URLs.

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

### Evidence providers

The public VerifyIt experience does not expose provider credentials or vendor-specific setup messages. Evidence providers implement the shared `EvidenceProvider` protocol and are selected through configuration.

Copy the repository example file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Select a registered provider:

```text
VERIFYIT_EVIDENCE_PROVIDER=<provider-id>
```

Bundled adapters currently include:

- `tavily` — simple API-key-based general web search, recommended for local MVP testing.
- `searxng` — points VerifyIt at an operator-controlled/self-hosted SearXNG instance with JSON search enabled.
- `google_factcheck` — optional published-fact-check adapter using OAuth credentials; not required for normal development.

Example local Tavily configuration:

```text
VERIFYIT_EVIDENCE_PROVIDER=tavily
TAVILY_API_KEY=your_key_here
```

Example SearXNG configuration:

```text
VERIFYIT_EVIDENCE_PROVIDER=searxng
SEARXNG_BASE_URL=https://your-search-instance.example
```

Developers can register another API, search service, RAG system, database, or self-hosted retriever without changing the verifier.

See `docs/evidence-providers.md` for the provider contract and extension instructions.

The `.env` file is ignored by Git and must never be committed.

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

For URLs, VerifyIt applies application-level SSRF defenses, follows only re-validated redirects, limits download size/time, extracts readable HTML/text, and reports login walls or unsupported media instead of inventing hidden content.

For social links, generic platform shells are classified as `platform_only`, not `accessed`. If only meaningful public post metadata is available, the result is `partial` and VerifyIt explicitly warns that media/context were not fully inspected.

For general web search, VerifyIt ranks candidate evidence using a documented heuristic. Government/official/academic/fact-check sources receive stronger authority priors than generic pages or social platforms, while relevance remains a major part of the score. **Authority ranking is not itself proof that a claim is true.**

For published fact checks, a reviewed claim must substantially match the submitted/extracted context, and matched normalized ratings must agree before a non-`UNVERIFIED` verdict is produced.

See `docs/evidence-pipeline.md` and `docs/evidence-providers.md` for details and limitations.

## Roadmap

1. **Implemented (retrieval/ranking):** general evidence providers and source ranking
2. **Next:** fetch top evidence pages and compare their actual content with the claim
3. **Implemented (MVP):** safe URL/content extraction
4. **Implemented (optional):** existing fact-check lookup
5. Scam and hidden-payment analysis
6. Screenshot/image input
7. Video/Reel analysis
8. Browser and Android share integrations
9. X/Instagram/WhatsApp adapters
10. Public verification pages and duplicate-claim detection

## Status

Early development. VerifyIt is not yet a production fact-checking service, and a verdict should always remain inspectable through its evidence.
