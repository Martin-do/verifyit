# VerifyIt

VerifyIt is an open-source, evidence-backed verification service for checking claims, links, posts, screenshots, and media before you believe, pay, click, or share.

## Mission

Make verification simple enough to use in the moment misinformation appears. VerifyIt should work across web and social platforms through multiple interfaces that all use one verification engine.

## Core principles

- **Evidence first:** verdicts must be grounded in retrieved evidence, not model intuition.
- **Transparent uncertainty:** `UNVERIFIED` is a valid result when evidence is insufficient.
- **Source quality matters:** official and primary sources are preferred over secondary summaries.
- **Plain-language output:** users should get a concise bottom line before deeper detail.
- **Cross-platform by design:** web, share-sheet, social bots, and messaging integrations should reuse the same backend.
- **Safety over engagement:** scam, phishing, financial, health, and other high-risk claims should surface clear warnings.

## Initial verdicts

- VERIFIED
- MOSTLY_TRUE
- MISLEADING
- UNVERIFIED
- FALSE
- SCAM_RISK

## MVP

The first milestone is a testable web/API prototype that accepts text or a URL, extracts the claim, gathers evidence, evaluates source quality, and returns a structured verdict with citations and confidence.

Platform-specific integrations come after the core verification engine is stable.

## Status

Early development.
