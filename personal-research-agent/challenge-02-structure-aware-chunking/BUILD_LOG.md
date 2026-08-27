# Build log

- **What broke:** The first test run exposed heading leakage: paragraph overlap survived a heading transition, so an Evaluation sentence was stored under Implementation. Heading transitions now flush without overlap.
- **What I learned:** Overlap is only safe inside a semantic section; paragraph-boundary overlap alone is insufficient if heading changes are ignored.
- **Evidence:** First run: `1 failed, 2 passed`; after the fix: `3 passed`. Ordered hashes and row counts are identical across two regenerations.
- **Next skill:** Embedding chunks and measuring retrieval quality with a labeled evaluation set.
