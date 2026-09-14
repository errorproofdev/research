# Working notes

- Inspected AGENTS.md, all research-agent branches, recent repository commits, and Challenge 7's BUILD_LOG before selecting this task.
- Challenge 7 handed off to a budgeted orchestrator with typed actions, loop limits, resumable state, idempotency, and deterministic replay.
- Kept the implementation dependency-free so orchestration semantics can be tested without a model, network, or hosted service.
- The first execution approach used SQLite and unittest discovery. The available isolated runner rejected subprocess and SQLite imports.
- Replaced the database prototype with one atomic JSON journal per run. State, calls, and events now move together through os.replace.
- Stored planner progress as the committed step count. A scripted planner can reproduce the next action after restart.
- Persisted a tool-call record before execution and passed its stable key into the handler.
- External exactly-once behavior still requires the tool to honor the idempotency key.
- Chained canonical event payloads with SHA-256 so edits, deletions, and reordering are detectable during replay.
- The runner also removes Python class construction, so the final production logic uses a small functional core with explicit dictionaries rather than hiding state transitions behind framework objects.
- Final isolated execution passed all five deterministic test groups.
