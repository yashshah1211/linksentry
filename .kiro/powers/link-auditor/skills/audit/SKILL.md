---
name: linksentry-link-audit
description: Review LinkSentry link parsing, normalization, deduplication, HTTP checking, and correctness behavior. Use when auditing or changing LinkSentry's URL-processing pipeline.
---

# LinkSentry Link Audit

When reviewing or modifying LinkSentry:

1. Follow `.kiro/steering/python-style.md`.
2. Keep extraction, normalization, deduplication, and classification pure.
3. Only `checker.py` may perform HTTP/network I/O.
4. Preserve normalization idempotence.
5. Preserve deduplication idempotence.
6. Ensure deduplicated output contains no duplicate values.
7. Ensure extracted URLs use only HTTP or HTTPS.
8. Keep HTTP classification deterministic.
9. Every network request must use a timeout.
10. Never disable TLS certificate verification.
11. Run the pytest suite after changing URL-processing behavior.