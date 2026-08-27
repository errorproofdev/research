# Personal Research Agent — Challenge 1: Ingestion boundary

A runnable FastAPI service that fetches an HTML article, extracts clean Markdown and metadata with Trafilatura, stores it in SQLite, and deduplicates mirrored content with SHA-256.

## Run it

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
uvicorn research_agent.main:app --reload
```

Then ingest a source:

```bash
curl -i http://127.0.0.1:8000/sources \
  -H 'content-type: application/json' \
  -d '{"url":"https://example.com/article"}'
```

The first request returns `201` and `created: true`. Re-ingesting identical extracted content—even through another URL—returns the existing ID with `200` and `created: false`. Full article content stays in SQLite and is intentionally omitted from the response.

## Failure contract

| Condition | Status |
|---|---:|
| Malformed or non-HTTP URL | 422 |
| Upstream timeout | 504 |
| Upstream/network failure | 502 |
| PDF, image, or other non-HTML media | 415 |
| HTML with no extractable article | 422 |

## Design decisions

- A 10-second HTTPX timeout, explicit user agent, and redirect following handle common ingestion failures.
- `Content-Type` parameters are stripped before media-type comparison.
- Normalized Markdown is the canonical content used for both storage and hashing.
- SQLite's unique constraint on `content_hash` is the final duplicate guard.
- Tests use HTTPX's in-memory transport, so error cases are deterministic and do not depend on the public internet.
