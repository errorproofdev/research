# Build log

- **What broke:** No functional failures. The run surfaced an upstream Starlette warning that its HTTPX-backed `TestClient` is deprecated in favor of `httpx2`.
- **What I learned:** Content-hash versioning makes embedding sync both idempotent and selective, while a tiny labeled set catches retrieval regressions that subjective inspection would miss.
- **Evidence:** `5 passed` on Python 3.12 in 0.98 seconds; the four-query fixture achieved `Recall@2 = 1.0` and satisfied `MRR >= 0.875`.
- **Likely failure points:** Provider row reordering, dimension drift, stale vectors after content changes, zero vectors, and visually plausible search results without labeled evaluation.
- **Next skill:** Hybrid BM25/vector retrieval with query-level failure analysis and reranking.
