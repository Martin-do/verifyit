# Verification Methodology

This document defines the initial trust rules for VerifyIt. The rules will evolve as the evaluation corpus grows.

## 1. Separate claims from content

A post may contain several claims. VerifyIt should identify the specific factual assertions that can be checked rather than assigning one truth label to an entire post by default.

## 2. Prefer primary evidence

Initial source preference:

1. Original official/primary source directly responsible for the claim or event
2. Official records, legislation, datasets, court documents, scientific papers, or institutional publications
3. Reputable independent fact-checking organisations
4. High-quality reporting that links to or directly quotes primary evidence
5. Other secondary sources

Search-result snippets, reposts, anonymous accounts, and generated summaries are not sufficient evidence by themselves.

## 3. Freshness is part of truth

A claim can have been true previously but be misleading now. Time-sensitive checks must record when the source was published or updated and when VerifyIt performed the check.

## 4. Verdict vocabulary

### VERIFIED
Strong evidence supports the material factual claim.

### MOSTLY_TRUE
The core claim is supported, but a limited detail, omission, or framing issue prevents a fully verified result.

### MISLEADING
The content uses true or partly true material in a way likely to create a materially incorrect impression, including missing context, old content presented as current, exaggerated headlines, or "free" offers with material undisclosed conditions.

### UNVERIFIED
Available evidence is insufficient, inaccessible, conflicting, or too weak to justify a factual verdict.

### FALSE
Reliable evidence directly contradicts the material factual claim.

### SCAM_RISK
The content shows material fraud, phishing, impersonation, deceptive-payment, credential-theft, or comparable risk signals. This label can coexist conceptually with factual findings; the response schema may later separate truth verdict from risk rating.

## 5. Confidence is not truth probability

The confidence field describes how strongly the retrieved evidence supports the assigned assessment. It must not be presented as a mathematically calibrated probability until calibration has been validated empirically.

## 6. Fail safely

When evidence retrieval fails, protected social content cannot be accessed, or the relevant part of a video cannot be inspected, the system must disclose that limitation. It must not silently infer what inaccessible content contains.

## 7. Explain the bottom line

Every completed verification should ultimately expose:

- the claim checked
- verdict
- concise bottom line
- supporting/contradicting evidence
- source links
- check date
- relevant limitations
- confidence descriptor

## 8. High-risk domains

Health, financial, legal, political/election, public-safety, and other consequential claims require stricter source standards and explicit uncertainty. The system should not elevate weak secondary evidence merely to avoid returning `UNVERIFIED`.
