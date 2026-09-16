# Working notes

- Inspected `AGENTS.md`, all remote `research-agent/*` branches, recent commits, and Challenge 8's build log before selecting the task.
- Challenge 8 handed off to an MCP boundary with capability scopes, per-tool approval, and conformance tests.
- The current 2026-07-28 MCP specification is stateless: requests carry protocol version and client capabilities in `_meta`; no initialization session is assumed.
- Tool discovery is filtered by the authenticated subject's scopes, but calls independently re-check scope so obscurity is never authorization.
- Sensitive calls return a machine-readable approval requirement before any side effect.
- Approval tokens are HMAC-signed, bound to subject/tool/canonical argument hash, expire quickly, and are consumed once.
- Persist consumed nonces atomically so restarting the stdio process does not revive an already-used approval.
- Audit entries record argument hashes rather than raw arguments to reduce accidental sensitive-data retention.
- Initial deterministic suite: 9 passed. Review then identified restart replay as an untested gap.
- Final suite: 10 passed after adding the persistent nonce ledger and restart test; the stdio `tools/list` smoke test also passed.
