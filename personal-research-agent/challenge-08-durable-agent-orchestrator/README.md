# Personal Research Agent — Challenge 8: Durable agent orchestration

This challenge turns the earlier retrieval, synthesis, security, and safe-fetch boundaries into a controlled execution loop. The orchestrator persists each run as an atomic JSON journal, validates typed tool actions, enforces hard budgets, resumes interrupted work with stable idempotency keys, and records a tamper-evident event trace.

## Run it

From this folder:

    PYTHONPATH=src python tests/test_orchestrator.py

No runtime or test dependencies are required beyond Python 3.11+.

## Product contract

- The functional planner can only emit a registered tool call or a final answer.
- Each tool declares required and optional arguments; missing and unexpected fields fail closed.
- Maximum steps and tool calls stop runaway agents.
- Run state and tool-call state survive process restarts.
- State, tool results, and trace events share one atomically replaced JSON journal.
- Tool idempotency keys are stable across retries.
- A tool interrupted after its side effect receives the same key when resumed.
- Each event includes the previous event hash, producing a verifiable SHA-256 chain.
- Replay reconstructs run status without invoking a planner or tool.

## Success check

The deterministic suite proves that:

1. A research run calls a typed search tool, finishes, and replays to the same state.
2. A simulated crash after a tool side effect resumes without duplicating that effect.
3. Step and tool-call budgets terminate runaway plans.
4. Missing, extra, and unknown tool inputs are rejected.
5. Editing a persisted event causes replay verification to fail.

Important: framework-level exactly-once delivery is impossible for arbitrary external side effects. Tools must honor the provided idempotency key. Atomic file replacement protects one writer; a production multi-worker service should move the same invariants into a transactional database with a lease or compare-and-swap claim.

## Roadmap

Ingest → chunk → retrieve/evaluate → hybrid rerank → cited synthesis → RAG red-team → safe fetch → durable orchestration ✓

Next: expose these tools through MCP with capability-scoped authorization, per-tool approvals, and protocol-level conformance tests.
