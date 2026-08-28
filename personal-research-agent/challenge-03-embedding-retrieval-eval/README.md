# Personal Research Agent — Challenge 3: Embeddings and retrieval evaluation

A standalone, measurable retrieval layer for the chunks produced in Challenge 2. It supports a deterministic offline baseline and an OpenAI-compatible hosted/local adapter, persists versioned float32 embeddings in SQLite, retrieves by cosine similarity, and evaluates labeled queries using Recall@K and mean reciprocal rank (MRR).

## Run it

```bash
uv sync --extra test
uv run pytest -q
uv run uvicorn research_agent.main:app --reload
```

## API loop

1. `POST /chunks` with the ordered chunks from the prior pipeline.
2. `POST /embeddings/sync` to embed only missing or content-stale rows.
3. `POST /search` with `{"query":"...", "limit":5}`.
4. `POST /evaluate?k=3` with labeled query/relevant-chunk pairs.

The default `HashingEmbedder` is an intentionally simple lexical baseline. It is deterministic, costs nothing, and makes pipeline regressions reproducible. Replace it at app construction with `OpenAICompatibleEmbedder` to test an actual semantic model exposed by a hosted service or local OpenAI-compatible runtime.

## Success contract

- Re-running unchanged embedding sync writes zero rows.
- Editing one chunk re-embeds exactly that chunk.
- Provider row count, dimension, and finite-value validation happen before any database write.
- The included four-query fixture must achieve `Recall@2 = 1.0` and `MRR >= 0.875`.
- Retrieval results have stable score ordering with chunk ID as a deterministic tie-breaker.

## Why evaluation comes now

Choosing a vector database or larger embedding model before establishing a labeled baseline hides whether changes actually help. This challenge deliberately keeps exact search small and transparent; the next challenge can add hybrid BM25/vector retrieval and reranking while measuring the delta against the same query set.
