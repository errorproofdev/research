# Build log

- **What broke:** The first dependency-sync/test command exceeded its 30-second output window while building the package. A cached rerun completed normally; no functional test failed. Starlette also emitted its known HTTPX `TestClient` deprecation warning.
- **What I learned:** Rank fusion avoids brittle cross-score normalization, and reporting candidate recall separately prevents a reranker from disguising an upstream retrieval miss.
- **Evidence:** `5 passed` on Python 3.12 in 0.58 seconds. The controlled exact-term query improved from dense `Recall@1 = 0.0` to hybrid and reranked `Recall@1 = 1.0`.
- **Likely failure points:** Raw FTS syntax injection, stale vector rows after chunk edits, incomparable score normalization, nondeterministic ties, candidate truncation, and reranker improvements that hide recall loss.
- **Next skill:** Citation-grounded answer synthesis that refuses unsupported claims and traces every sentence to retrieved chunks.
