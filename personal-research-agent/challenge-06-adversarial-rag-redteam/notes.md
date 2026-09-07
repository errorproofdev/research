# Working notes

- Inspected the remote Challenge 5 build log and all research-agent branches before choosing this task.
- Challenge 5 explicitly handed off to adversarial RAG testing.
- Place a deterministic evidence gateway after retrieval and before generation so every model adapter receives the same sanitized, tenant-scoped evidence.
- Quarantine direct and base64-encoded prompt injection instead of asking the model to ignore it.
- Treat citations found inside retrieved text as untrusted content; only the synthesis verifier may create trusted source labels.
- Remove cross-tenant chunks before any prompt construction and redact recognized secret formats from remaining evidence.
- Refuse explicit prompt, credential, secret, and environment-variable exfiltration requests before processing sources.
- Score attacks and benign traffic separately to expose defenses that achieve safety by refusing everything.
- Executed seven deterministic tests across direct injection, encoded injection, poisoned metadata, fake citations, secret redaction, tenant isolation, exfiltration refusal, benign traffic, red-team metrics, and the API route. All passed.
