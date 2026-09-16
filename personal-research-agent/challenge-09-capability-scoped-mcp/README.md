# Personal Research Agent — Challenge 9: Capability-scoped MCP

A stateless MCP boundary for exposing research-agent tools without giving every client every capability. It implements the current `2026-07-28` request metadata model, filters tool discovery by scope, re-authorizes every call, and requires argument-bound one-time approval for external fetches.

## Run it

```bash
uv sync --extra test
uv run pytest -q
```

Start the JSON-lines stdio server with a secret of at least 32 bytes:

```bash
export RESEARCH_AGENT_MCP_SECRET='replace-with-a-random-secret-at-least-32-bytes'
export RESEARCH_AGENT_MCP_SCOPES='research:read,research:fetch'
export RESEARCH_AGENT_MCP_APPROVAL_STATE='./state/consumed-approvals.json'
uv run research-agent-mcp
```

## Security contract

- Every request must declare MCP protocol version and client capabilities in `_meta`.
- `tools/list` only reveals tools allowed by the subject's scopes.
- `tools/call` repeats authorization and JSON Schema input checks.
- `research_fetch` cannot execute without explicit approval.
- Approval tokens are HMAC-signed and bound to subject, tool, exact canonical arguments, expiration, and a one-time nonce persisted across restarts.
- Handler failures return a stable public error without internal exception text.
- Audit entries retain argument hashes, not raw values.
- The MCP layer queues an approved fetch; the SSRF-resistant network boundary from Challenge 7 remains responsible for transport security.

## Success check

The deterministic suite proves scoped discovery, authorized reads, denial without scope, approval-required behavior before side effects, valid execution, replay rejection, argument binding, expiry, protocol/schema enforcement, sanitized failures, and audit evidence.

## Roadmap

Ingest → chunk → retrieve/evaluate → rerank → cited synthesis → RAG red-team → safe fetch → durable orchestration → capability-scoped MCP ✓

Next: package the service boundaries with Docker Compose, health checks, non-root containers, persistent volumes, secret injection, and a deployment smoke test.

## References

- [MCP 2026-07-28 changes](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- [MCP tool protocol and safety guidance](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
