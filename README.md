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

VerifyIt 0.2 can inspect accessible public HTTP/HTTPS pages and can use a configured evidence provider. The repository currently ships one published-fact-check adapter as an MVP example, but the verification engine itself is provider-neutral.

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

A registered provider can be selected with:

```text
VERIFYIT_EVIDENCE_PROVIDER=<provider-id>
```

The repository includes an optional bundled published-fact-check adapter for development/testing. Its current upstream service requires OAuth-authenticated credentials, so the adapter uses Google Application Default Credentials (ADC) rather than an API key. Developers can instead register another API, search service, RAG system, database, or self-hosted retriever without changing the verifier.

For local ADC setup, install the Google Cloud CLI and create credentials with the required Fact Check Tools scope. Because this is a non-default OAuth scope, use your own OAuth client configuration when creating local ADC credentials:

```bash
gcloud auth application-default login \
  --client-id-file=PATH_TO_CLIENT_JSON \
  --scopes=https://www.googleapis.com/auth/factchecktools,https://www.googleapis.com/auth/cloud-platform
```

VerifyIt then discovers those credentials automatically through `google-auth`. Production deployments should use an appropriate ADC-supported workload identity rather than storing secrets in the repository.

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

For published evidence, a search result is not automatically treated as truth. The reviewed claim must substantially match the submitted/extracted context, and matched normalized ratings must agree before a non-`UNVERIFIED` verdict is produced.

See `docs/evidence-pipeline.md` and `docs/evidence-providers.md` for details and limitations.

## Roadmap

1. **In progress:** general evidence providers and source ranking beyond existing fact checks
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
