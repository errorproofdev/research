# Personal Research Agent — Challenge 6: Adversarial RAG gateway

A standalone security boundary and regression harness for the citation-grounded RAG pipeline from Challenge 5. It treats retrieved documents as untrusted input before any text reaches a model.

## Run it

```bash
uv sync --extra test
uv run pytest -q
uv run uvicorn research_agent.main:app --reload
```

Send `POST /security/prepare` with the question, active tenant ID, and retrieved chunks. The gateway returns only safe tenant-scoped evidence plus structured security events, or refuses before generation.

## Threat controls

- Direct and base64-encoded source prompt injection is quarantined.
- Injection in titles and headings is treated as poisoned metadata.
- Fake `[S99]` source labels are replaced with visibly untrusted markers.
- Recognized API keys, access tokens, passwords, and AWS access keys are redacted.
- Foreign-tenant evidence is removed before prompt construction.
- Requests to expose prompts, credentials, secrets, or environment variables are refused.
- Empty safe evidence fails closed.

This is a deterministic defense layer, not a claim that regexes solve prompt injection. Unknown encodings, novel secret formats, semantic attacks, and false positives remain explicit risks. The red-team suite turns every discovered bypass into a permanent regression case.

## Success contract

- Seven tests cover direct and encoded injection, poisoned metadata, citation laundering, secret redaction, tenant isolation, exfiltration refusal, benign traffic, and the FastAPI route.
- The four-case red-team fixture must achieve `case_pass_rate = 1.0`, `attack_handled_rate = 1.0`, and `benign_pass_rate = 1.0` with `secret_leak_rate = 0.0`.
- Attack handling and benign pass-through are reported separately so blanket refusal cannot look successful.

Next: give the agent a network tool without giving it access to loopback, private infrastructure, unlimited redirects, unlimited downloads, or unaudited browsing.
