from __future__ import annotations

from dataclasses import dataclass

from .embeddings import Embedder
from .store import Database


@dataclass(frozen=True)
class EvaluationCase:
    query: str
    relevant_chunk_ids: frozenset[int]


def evaluate_retrieval(
    db: Database,
    embedder: Embedder,
    cases: list[EvaluationCase],
    k: int = 3,
) -> dict:
    if not cases:
        raise ValueError("Evaluation set cannot be empty")
    hits = 0
    reciprocal_ranks = 0.0
    details = []
    for case in cases:
        results = db.search(case.query, embedder, limit=k)
        ranked_ids = [row["id"] for row in results]
        first_rank = next(
            (index for index, chunk_id in enumerate(ranked_ids, start=1) if chunk_id in case.relevant_chunk_ids),
            None,
        )
        hits += first_rank is not None
        reciprocal_ranks += 1 / first_rank if first_rank else 0
        details.append({"query": case.query, "ranked_chunk_ids": ranked_ids, "first_relevant_rank": first_rank})
    return {
        "query_count": len(cases),
        f"recall_at_{k}": hits / len(cases),
        "mrr": reciprocal_ranks / len(cases),
        "details": details,
    }

