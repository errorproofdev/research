# Personal Research Agent — Challenge 7: SSRF-safe research fetch

A standalone network boundary for safely giving the research agent a webpage-fetch tool. It validates and pins public IP addresses, revalidates every redirect, enforces domain/port/request/redirect/byte budgets, and records a cryptographic provenance trace.

## Run it

```bash
uv sync --extra test
uv run pytest -q
uv run uvicorn research_agent.main:app --reload
```

`POST /research/fetch` accepts a URL, optional domain allowlist, and bounded fetch budget. The response includes the final body and a trace of every completed hop.

## Security contract

- Only HTTP and HTTPS on ports 80 and 443 are accepted.
- Userinfo, localhost, and every non-global IPv4/IPv6 category are rejected.
- Every DNS answer must be public; mixed public/private answers fail closed.
- The socket connects directly to one validated IP while retaining hostname-based TLS verification.
- The connected peer IP must belong to that exact validated answer set.
- Every redirect repeats URL, domain, port, DNS, and IP validation.
- HTTPS-to-HTTP downgrade is forbidden.
- Request count, redirect count, timeout, and total downloaded bytes are bounded.
- `Accept-Encoding: identity` keeps byte accounting aligned with the body read.
- Each trace entry records the canonical URL, DNS answers, peer IP, response status, redirect location, byte count, and SHA-256.

## Success contract

- Loopback, link-local metadata, private IPv4, IPv6 loopback, and mixed DNS answers are blocked.
- Allowlist suffix confusion such as `example.com.evil.test` is blocked.
- A redirect to `169.254.169.254` is rejected before a second request.
- A connected peer outside the validated DNS set is rejected.
- Byte, redirect, and HTTPS downgrade policies fail closed.
- A valid two-host redirect produces two independently verified provenance entries.

Next: wrap the safe tools in a budgeted orchestration loop with typed actions, resumable state, idempotency, and deterministic replay.
