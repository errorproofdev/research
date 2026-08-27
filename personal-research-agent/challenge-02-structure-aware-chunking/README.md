# Personal Research Agent — Challenge 2: Structure-aware chunking

A standalone continuation of Challenge 1 that stores extracted articles as Markdown and regenerates searchable chunks without splitting fenced code, losing heading context, or creating duplicate rows.

## Run it

```bash
uv sync --extra test
uv run pytest -q
uv run uvicorn research_agent.main:app --reload
```

Ingest a source with `POST /sources`, then create or regenerate its chunks:

```bash
curl -X POST http://127.0.0.1:8000/sources/1/chunks
```

## Invariants

- Markdown is parsed into headings, paragraphs, and atomic fenced-code blocks before token budgeting.
- Normal chunks never exceed `max_tokens`; a code block that exceeds the limit remains intact and is marked `oversized=true`.
- Oversized prose is split by sentence and then word boundary as a final fallback.
- Each chunk is prefixed with its full heading path and overlap occurs only at paragraph boundaries.
- Chunk indexes are contiguous and SHA-256 hashes are stable across reruns.
- Regeneration replaces one source's chunks inside a single transaction, preventing partial deletion on failure.

## Schema

`chunks(id, source_id, chunk_index, heading_path, content, token_count, start_offset, end_offset, content_hash, oversized)`

The included fixture has nested headings, a 100-line fenced code block, oversized prose, and repeated text under adjacent sections. Tests verify size limits, intact code, deterministic hashes and row counts, contiguous ordering, paragraph coverage, and database lookup by distinctive sentence.
