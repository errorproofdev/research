from __future__ import annotations

from fastapi.testclient import TestClient

from research_agent.embeddings import HashingEmbedder
from research_agent.engine import HybridEngine
from research_agent.evaluation import EvaluationCase, classify_failure, evaluate
from research_agent.main import create_app
from research_agent.rerank import CoverageReranker

CHUNKS = [
    {"source_id": 1, "chunk_index": 0, "heading_path": "SQLite > FTS5", "content": "SQLite FTS5 BM25 exact keyword retrieval handles identifiers and rare terms."},
    {"source_id": 1, "chunk_index": 1, "heading_path": "Vectors > Semantics", "content": "Dense semantic vector search answers conceptual questions with embeddings."},
    {"source_id": 2, "chunk_index": 0, "heading_path": "Fusion > RRF", "content": "Reciprocal rank fusion combines lexical and vector ranked lists."},
    {"source_id": 2, "chunk_index": 1, "heading_path": "Security > SSRF", "content": "Server side request forgery defenses block private network addresses and redirects."},
]


class LookupEmbedder:
    model, dimension = "controlled-eval-v1", 2

    def __init__(self):
        self.mapping = {
            "SQLite > FTS5\n" + CHUNKS[0]["content"]: [1.0, 0.0],
            "Vectors > Semantics\n" + CHUNKS[1]["content"]: [0.0, 1.0],
            "Fusion > RRF\n" + CHUNKS[2]["content"]: [0.7, 0.7],
            "Security > SSRF\n" + CHUNKS[3]["content"]: [-1.0, 0.0],
            "SQLite FTS5 BM25": [0.0, 1.0],
        }

    def embed(self, texts):
        return [self.mapping.get(text, [0.0, 1.0]) for text in texts]


def controlled_engine(tmp_path):
    engine = HybridEngine(tmp_path / "hybrid.db", LookupEmbedder(), CoverageReranker())
    ids = engine.upsert_chunks(CHUNKS)
    assert engine.index_vectors() == 4
    return engine, ids


def test_hybrid_recovers_dense_miss_and_measures_delta(tmp_path):
    engine, ids = controlled_engine(tmp_path)
    case = EvaluationCase("SQLite FTS5 BM25", frozenset({ids[0]}))
    report = evaluate(engine, [case], k=1)
    assert report["dense"]["recall_at_1"] == 0.0
    assert report["hybrid"]["recall_at_1"] == 1.0
    assert report["reranked"]["recall_at_1"] == 1.0
    assert report["details"][0]["failure_type"] == "success"


def test_raw_fts_syntax_is_tokenized_not_executed(tmp_path):
    engine, ids = controlled_engine(tmp_path)
    results = engine.lexical_search('SQLite" OR content:forgery NOT (', 10)
    assert {row["id"] for row in results} >= {ids[0], ids[3]}


def test_failure_taxonomy_distinguishes_candidate_and_ranking_errors():
    relevant = frozenset({9})
    assert classify_failure([9, 2], [9, 2], relevant, 1) == "success"
    assert classify_failure([2, 9], [2, 9], relevant, 1) == "ranking_failure"
    assert classify_failure([2, 3], [2, 3], relevant, 1) == "candidate_miss"


def test_tie_breaks_are_stable(tmp_path):
    engine, _ = controlled_engine(tmp_path)
    first = [row["id"] for row in engine.search("unseen vocabulary", rerank=False)]
    second = [row["id"] for row in engine.search("unseen vocabulary", rerank=False)]
    assert first == second


def test_api_success_loop(tmp_path):
    app = create_app(tmp_path / "api.db", HashingEmbedder(dimension=256), CoverageReranker())
    client = TestClient(app)
    ids = client.post("/chunks", json=CHUNKS).json()["chunk_ids"]
    assert client.post("/index").json() == {"indexed": 4}
    result = client.post("/search", json={"query": "reciprocal rank fusion lexical vector", "limit": 1}).json()["results"][0]
    assert result["id"] == ids[2]
    report = client.post("/evaluate?k=2", json=[{"query": "private network SSRF redirects", "relevant_chunk_ids": [ids[3]]}]).json()
    assert report["reranked"]["recall_at_2"] == 1.0

