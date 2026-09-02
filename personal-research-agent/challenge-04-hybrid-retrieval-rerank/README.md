# Personal Research Agent — Challenge 4: Hybrid retrieval and reranking

A standalone retrieval upgrade that combines SQLite FTS5/BM25 with dense vectors, fuses their ranks using weighted reciprocal-rank fusion (RRF), optionally reranks the candidate set, and reports where each labeled query fails.

## Run it

```bash
uv sync --extra test
uv run pytest -q
uv run uvicorn research_agent.main:app --reload
```

## API loop

1. `POST /chunks` with structure-aware chunks.
2. `POST /index` to embed unindexed rows.
3. `POST /search` with a query, result limit, candidate limit, and optional reranking.
4. `POST /evaluate?k=3` with labeled query/relevant-chunk pairs.

Search results expose `lexical_rank`, `dense_rank`, `fusion_score`, and `rerank_score`, making the pipeline inspectable instead of returning an unexplained final score.

## Success contract

- Raw punctuation and FTS operators cannot alter the generated MATCH expression.
- Weighted RRF combines ranks without pretending BM25 and cosine scores share a scale.
- Stable chunk-ID tie-breaking makes repeated searches deterministic.
- The controlled evaluation fixture deliberately makes dense retrieval miss an exact technical query; hybrid retrieval must improve `Recall@1` from `0.0` to `1.0`.
- Per-query analysis distinguishes `candidate_miss`, `ranking_failure`, and `success`.
- The reranker cannot hide candidate recall because dense, hybrid, and reranked metrics are reported separately.

## Next decision

The next product boundary is citation-grounded synthesis: generate an answer only from retrieved chunks, attach sentence-level source references, and refuse claims that lack evidence. That makes retrieval quality visible to the final user instead of stopping at ranked search results.
