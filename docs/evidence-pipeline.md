# Evidence pipeline

VerifyIt 0.2 adds two grounded inputs to the verification flow: safe URL extraction and published fact-check retrieval.

## URL extraction

For `http://` and `https://` inputs, VerifyIt:

1. normalizes the URL and removes fragments;
2. rejects embedded credentials and non-standard ports;
3. rejects localhost, private, loopback, link-local, reserved, multicast, and unspecified IP targets;
4. re-validates each redirect target;
5. limits redirects, timeout, and response size;
6. extracts readable text from HTML while dropping scripts/styles;
7. reports blocked/login-wall social content instead of inferring what is hidden.

This is an application-level SSRF defense. Production deployment should additionally enforce outbound-network restrictions at the infrastructure layer because DNS rebinding and proxy/network configuration can create risks beyond application validation.

## Published fact checks

When `GOOGLE_FACT_CHECK_API_KEY` is configured, VerifyIt queries the Google Fact Check Tools `claims.search` endpoint for published ClaimReview records.

A search result does not automatically become a verdict. VerifyIt compares the reviewed claim with the submitted/extracted context and requires a minimum match score. It then normalizes only a conservative set of common textual ratings. If matching reviews disagree, the verdict remains `UNVERIFIED`.

Current limitation: Google Fact Check search only helps when a relevant claim has already been reviewed by a participating publisher. It is not a general web-search or primary-source evidence engine. That is the next evidence-provider milestone.
