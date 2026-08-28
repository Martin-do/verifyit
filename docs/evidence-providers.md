# Evidence providers

VerifyIt's verification engine is provider-neutral. The core verifier does not know or care which search API, fact-check index, RAG service, database, or self-hosted retriever supplies evidence.

## Provider contract

Providers implement the `EvidenceProvider` protocol in `backend/app/services/evidence_provider.py`:

```python
class EvidenceProvider(Protocol):
    provider_id: str

    def search(self, query: str, context: str) -> list[FactCheckHit]:
        ...
```

A provider is registered with `register_evidence_provider(provider_id, factory)`. The verifier obtains the configured provider through `get_configured_evidence_provider()` and calls only its generic `search()` method.

This keeps the public product and verification flow independent of any vendor.

## Bundled MVP adapter

The repository currently includes one bundled adapter for Google's Fact Check Tools API. It is an implementation example, not a product dependency. Developers may add another provider or replace it entirely.

To select a registered provider, set:

```text
VERIFYIT_EVIDENCE_PROVIDER=<provider-id>
```

For the bundled adapter:

```text
VERIFYIT_EVIDENCE_PROVIDER=google_factcheck
GOOGLE_FACT_CHECK_API_KEY=<key>
```

Provider credentials belong in `.env` or the deployment secret store. They must not be exposed in user-facing responses.

## Adding a custom provider

1. Implement `EvidenceProvider`.
2. Convert provider results into the shared evidence-hit shape expected by the verifier.
3. Register a factory under a unique provider id.
4. Select that provider through configuration.
5. Keep provider-specific credentials and errors behind the adapter boundary.

Future provider adapters may include general web search, primary-source search, organization-specific corpora, or self-hosted retrieval systems.
