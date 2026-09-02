# Build log

- **What broke:** No functional test failed. Starlette emitted its known deprecation warning for the HTTPX-backed `TestClient`.
- **What I learned:** Citation formatting is not grounding; trust comes from verifying structured claims against only the cited retrieved chunks before any source labels are rendered.
- **Evidence:** `6 passed` on Python 3.12 in 0.55 seconds. Supported claims received sentence-level sources, the invented-number case failed closed, and the refusal fixture achieved `refusal_accuracy = 1.0`.
- **Likely failure points:** Missing citations, citations outside the retrieved set, invented numbers, low-overlap paraphrases, model output that violates the JSON schema, source prompt injection, and partial answers that mix supported and unsupported claims.
- **Next skill:** Adversarial RAG testing for source prompt injection, poisoned documents, citation laundering, and retrieval exfiltration attempts.
