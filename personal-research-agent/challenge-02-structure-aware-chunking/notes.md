# Working notes

- Created an independent worktree from `main` on `research-agent/02-structure-aware-chunking`.
- Kept this challenge standalone by including the ingestion boundary alongside the chunker.
- Parse Markdown into typed blocks before considering token limits; code fences therefore remain atomic.
- Use `cl100k_base` through Tiktoken for deterministic counts instead of character estimates.
- Regeneration uses a single SQLite transaction: delete old rows, insert the complete new ordered set, then commit.
- The initial database lookup test caught heading leakage caused by retaining overlap across a section change. Changed heading-boundary flushes to disable overlap.
- Re-executed the suite after the fix: all 3 tests passed in 1.46 seconds.
