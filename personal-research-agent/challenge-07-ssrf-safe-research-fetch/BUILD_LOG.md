# Build log

- **What broke:** The first red-team fixture redirected from HTTPS to an HTTP metadata URL. The downgrade guard correctly rejected it before URL/IP revalidation, so the test did not prove the intended boundary. Changing the fixture to an HTTPS metadata URL exercised redirect revalidation; the independent downgrade test still covers protocol regression.
- **What I learned:** DNS filtering is only trustworthy when the transport connects to the validated address, preserves the original hostname for TLS, and verifies the actual peer. Security tests also need to isolate one control at a time so an earlier guard cannot create misleading coverage.
- **Evidence:** `uv run pytest -q` → `12 passed, 2 warnings in 0.23s`. The warnings are upstream Starlette/AnyIO test-client deprecations; no functional failure remains.
- **Likely failure points:** DNS rebinding, mixed public/private answers, alternative IP encodings, redirects to metadata services, HTTPS downgrade, unbounded redirect bodies, decompression bombs, proxy inheritance, hostname/SNI mismatch, and audit logs that record requested rather than connected addresses.
- **Next skill:** A budgeted research-agent orchestrator with explicit tool schemas, loop limits, resumable state, idempotency keys, and replayable execution traces.
