# Working notes

- Inspected the live research-agent branches and Challenge 3 build log before choosing this task.
- Challenge 3 explicitly handed off to hybrid BM25/vector retrieval, failure analysis, and reranking.
- Used SQLite FTS5 so lexical retrieval remains self-hostable and ships with the existing SQLite-oriented architecture.
- Tokenize raw queries before constructing FTS5 MATCH expressions; user-supplied operators and column syntax never reach the parser.
- Fuse lexical and dense rankings with weighted reciprocal-rank fusion rather than trying to normalize incomparable BM25 and cosine scores.
- Put reranking behind a protocol. The included coverage reranker is transparent and deterministic; a cross-encoder can replace it without changing retrieval or evaluation.
- Evaluation compares three stages and labels failures as candidate misses or ranking failures, making the next optimization target explicit.
- Executed five deterministic tests covering dense-miss recovery, raw FTS syntax handling, failure taxonomy, stable tie-breaking, and the full FastAPI loop. All passed.
