# Build log

- **What broke:** No functional test failed. Starlette emitted deprecation warnings for its HTTPX `TestClient` integration and AnyIO `BlockingPortal` alias.
- **What I learned:** Attack blocking and benign pass-through must be measured separately; otherwise a policy that refuses every request appears perfectly secure. Tenant filtering and secret removal must happen before prompt construction, not after generation.
- **Evidence:** `7 passed` on Python 3.12 in 0.79 seconds. The four-case suite achieved `case_pass_rate = 1.0`, `attack_handled_rate = 1.0`, `benign_pass_rate = 1.0`, and `secret_leak_rate = 0.0`.
- **Likely failure points:** Obfuscated instructions, false positives in security articles, secrets outside known formats, poisoned titles, fake citations that survive rendering, cross-tenant cache keys, and a high attack-block rate caused by refusing benign questions.
- **Next skill:** An SSRF-resistant browser/research tool with DNS and redirect revalidation, domain policy, fetch budgets, provenance, and auditable tool traces.
