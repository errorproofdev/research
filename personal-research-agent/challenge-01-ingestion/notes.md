# Working notes

- Created a new worktree from `main` on `research-agent/01-ingestion`.
- Chose the standard-library `sqlite3` API to keep the persistence boundary explicit.
- Injected an HTTPX transport into the app factory so every network failure is reproducible in tests.
- Deduplicate on normalized extracted content, not URL, because mirrors and tracking URLs can point to the same article.
- Executed the full suite: all 5 tests passed in 1.51 seconds.
