# Build log

- **What broke:** No functional failures. The test run surfaced upstream Starlette deprecation warnings for the current TestClient and HTTP 422 constant.
- **What I learned:** Injecting HTTPX's transport makes redirects, media types, timeouts, extraction failures, and cross-URL duplicate handling fully deterministic.
- **Evidence:** `5 passed` with pytest on Python 3.12.
- **Next skill:** Chunking documents without destroying headings, code blocks, or citation context.
