# Evidence providers

VerifyIt's verification engine is provider-neutral. The core verifier does not know or care which search API, fact-check index, RAG service, database, or self-hosted retriever supplies evidence.

## Provider contract

Providers implement the `EvidenceProvider` protocol in `backend/app/services/evidence_provider.py`:

```python
class EvidenceProvider(Protocol):
    provider_id: str

    def search(self, query: str, context: str) -> list[EvidenceHit]:
        ...
```

`EvidenceHit` is the shared provider-neutral candidate shape. Providers may fill fields such as title, URL, snippet, publication date, provider score, published rating, or claim-match score depending on what their upstream service exposes.

A provider is registered with `register_evidence_provider(provider_id, factory)`. The verifier obtains the explicitly selected provider through `get_configured_evidence_provider()` and calls only its generic `search()` method.

## Bundled providers

### Tavily

Provider id:

```text
tavily
```

Configuration:

```text
VERIFYIT_EVIDENCE_PROVIDER=tavily
TAVILY_API_KEY=<key>
```

The adapter performs general web search and converts results into `EvidenceHit` records. VerifyIt then applies its own source ranking rather than accepting the upstream rank as a truth score.

### SearXNG

Provider id:

```text
searxng
```

Configuration:

```text
VERIFYIT_EVIDENCE_PROVIDER=searxng
SEARXNG_BASE_URL=https://your-instance.example
```

The configured SearXNG instance must allow JSON output. This adapter is useful for operators who want an open/self-hosted search layer. The base URL is trusted operator configuration, not user input.

### Google published fact checks (optional)

Provider id:

```text
google_factcheck
```

This adapter queries an existing published-fact-check index and currently requires OAuth credentials. It is optional and is not required for general VerifyIt development.

## Source ranking

General search results are ranked after retrieval using a documented heuristic combining:

- source-authority prior,
- query/result relevance,
- provider relevance score when supplied,
- freshness as a small factor.

Government/official/academic/fact-check sources receive stronger authority priors than generic web pages or social platforms. This ranking only decides which evidence candidates should be inspected first; it does **not** prove that a claim is true.

## Trust boundary

Search-result snippets are discovery material, not final evidence. The current general-search milestone returns ranked sources but keeps the factual verdict `UNVERIFIED`. The next evidence-synthesis layer will fetch selected source pages, extract relevant passages, compare those passages with the claim, and require traceable support/contradiction before assigning a verdict.

## Adding a custom provider

1. Implement `EvidenceProvider`.
2. Convert upstream results into `EvidenceHit` records.
3. Register a factory under a unique provider id.
4. Select that provider through `VERIFYIT_EVIDENCE_PROVIDER`.
5. Keep provider-specific credentials and errors behind the adapter boundary.
6. Never treat a provider's relevance/ranking score as a factual truth score.
