# Build log

- **What broke:** The first implementation consumed approval nonces only in memory. Its tests passed, but a process restart would have made a previously used token valid again. The nonce ledger is now atomically persisted, and a restart-replay regression test proves the fix.
- **What I learned:** Scoped discovery improves least privilege but cannot replace call-time authorization. Likewise, a signed approval is not truly one-time unless replay state survives restarts and the signature is bound to the subject, tool, and exact canonical arguments.
- **Evidence:** `uv run pytest -q` → `10 passed in 0.02s`. A JSON-lines stdio smoke test returned a valid `tools/list` response containing only the `research:read` tool and current protocol/server metadata.
- **Likely failure points:** trusting filtered discovery as authorization, approval tokens not bound to exact arguments, replayable approvals, leaking handler exceptions, logging raw secrets, accepting old protocol versions silently, sharing one authorization context across users, and exposing network tools without the SSRF-safe boundary.
- **Next skill:** Package the research-agent services with Docker Compose, health checks, non-root containers, persistent volumes, secrets, and a deployment smoke test.
