from __future__ import annotations

from dataclasses import dataclass

from .engine import HybridEngine


@dataclass(frozen=True)
class EvaluationCase:
    query: str
    relevant_chunk_ids: frozenset[int]


def metrics(rankings: list[list[int]], cases: list[EvaluationCase], k: int) -> dict:
    hits = 0
    reciprocal_ranks = 0.0
    for ranking, case in zip(rankings, cases):
        rank = next((position for position, chunk_id in enumerate(ranking[:k], 1) if chunk_id in case.relevant_chunk_ids), None)
        hits += rank is not None
        reciprocal_ranks += 1 / rank if rank else 0
    return {f"recall_at_{k}": hits / len(cases), "mrr_at_k": reciprocal_ranks / len(cases)}


def classify_failure(ranking: list[int], candidates: list[int], relevant: frozenset[int], k: int) -> str:
    if relevant.intersection(ranking[:k]):
        return "success"
    if not relevant.intersection(candidates):
        return "candidate_miss"
    return "ranking_failure"


def evaluate(engine: HybridEngine, cases: list[EvaluationCase], k: int = 3, candidate_limit: int = 20) -> dict:
    if not cases:
        raise ValueError("Evaluation set cannot be empty")
    dense_rankings, hybrid_rankings, reranked_rankings, details = [], [], [], []
    for case in cases:
        dense = engine.dense_search(case.query, candidate_limit)
        lexical = engine.lexical_search(case.query, candidate_limit)
        hybrid = engine.fuse(lexical, dense)
        reranked = engine.reranker.rerank(case.query, hybrid)
        dense_ids = [row["id"] for row in dense]
        hybrid_ids = [row["id"] for row in hybrid]
        reranked_ids = [row["id"] for row in reranked]
        dense_rankings.append(dense_ids)
        hybrid_rankings.append(hybrid_ids)
        reranked_rankings.append(reranked_ids)
        details.append({
            "query": case.query,
            "relevant_chunk_ids": sorted(case.relevant_chunk_ids),
            "dense_top_ids": dense_ids[:k],
            "hybrid_top_ids": hybrid_ids[:k],
            "reranked_top_ids": reranked_ids[:k],
            "failure_type": classify_failure(reranked_ids, hybrid_ids[:candidate_limit], case.relevant_chunk_ids, k),
        })
    return {
        "query_count": len(cases),
        "dense": metrics(dense_rankings, cases, k),
        "hybrid": metrics(hybrid_rankings, cases, k),
        "reranked": metrics(reranked_rankings, cases, k),
        "details": details,
    }

