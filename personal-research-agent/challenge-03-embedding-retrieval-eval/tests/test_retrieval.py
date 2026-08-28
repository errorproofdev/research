from __future__ import annotations

import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from research_agent.embeddings import HashingEmbedder, OpenAICompatibleEmbedder
from research_agent.evaluation import EvaluationCase, evaluate_retrieval
from research_agent.main import create_app
from research_agent.store import Database


CHUNKS = [
    {"source_id": 1, "chunk_index": 0, "heading_path": "Ingestion > Errors", "content": "HTTP timeouts redirects content type validation and duplicate article hashes."},
    {"source_id": 1, "chunk_index": 1, "heading_path": "Chunking > Structure", "content": "Markdown headings paragraphs overlap and fenced code blocks remain intact."},
    {"source_id": 2, "chunk_index": 0, "heading_path": "Retrieval > Evaluation", "content": "Embedding vectors cosine similarity labeled queries recall at k and mean reciprocal rank."},
    {"source_id": 2, "chunk_index": 1, "heading_path": "Deployment > Runtime", "content": "Docker containers health checks persistent volumes logs and rollback."},
]


def seeded(tmp_path):
    db = Database(tmp_path / "retrieval.db")
    ids = db.upsert_chunks(CHUNKS)
    embedder = HashingEmbedder(dimension=256)
    return db, embedder, ids


def test_embedding_sync_is_idempotent_and_content_versioned(tmp_path):
    db, embedder, ids = seeded(tmp_path)
    assert db.sync_embeddings(embedder) == {"embedded": 4, "skipped": 0}
    assert db.sync_embeddings(embedder) == {"embedded": 0, "skipped": 4}
    changed = {**CHUNKS[0], "content": CHUNKS[0]["content"] + " Retry budgets."}
    db.upsert_chunks([changed])
    assert db.sync_embeddings(embedder) == {"embedded": 1, "skipped": 3}


def test_labeled_retrieval_meets_quality_floor(tmp_path):
    db, embedder, ids = seeded(tmp_path)
    db.sync_embeddings(embedder)
    cases = [
        EvaluationCase("How do we handle HTTP timeout and duplicate content?", frozenset({ids[0]})),
        EvaluationCase("Keep fenced code blocks intact while chunking Markdown", frozenset({ids[1]})),
        EvaluationCase("Measure cosine retrieval using recall and reciprocal rank", frozenset({ids[2]})),
        EvaluationCase("Container health checks and persistent volume rollback", frozenset({ids[3]})),
    ]
    report = evaluate_retrieval(db, embedder, cases, k=2)
    assert report["recall_at_2"] == 1.0
    assert report["mrr"] >= 0.875


def test_invalid_provider_batch_writes_nothing(tmp_path):
    db, _, _ = seeded(tmp_path)

    class BrokenEmbedder:
        provider, model, dimension = "broken", "bad-dimension", 3
        def embed(self, texts):
            return [[1.0, 2.0] for _ in texts]

    with pytest.raises(ValueError, match="wrong dimension"):
        db.sync_embeddings(BrokenEmbedder())
    with sqlite3.connect(tmp_path / "retrieval.db") as connection:
        assert connection.execute("SELECT count(*) FROM embeddings").fetchone()[0] == 0


def test_openai_compatible_adapter_contract():
    def handler(request: httpx.Request):
        assert request.url.path == "/v1/embeddings"
        assert request.headers["authorization"] == "Bearer secret"
        assert b'"model":"test-model"' in request.content
        return httpx.Response(200, json={"data": [{"index": 1, "embedding": [0.0, 1.0]}, {"index": 0, "embedding": [1.0, 0.0]}]})

    adapter = OpenAICompatibleEmbedder("test-model", 2, "https://embedding.test", "secret", httpx.MockTransport(handler))
    assert adapter.embed(["first", "second"]) == [[1.0, 0.0], [0.0, 1.0]]


def test_api_success_check(tmp_path):
    app = create_app(tmp_path / "api.db", HashingEmbedder(dimension=256))
    client = TestClient(app)
    ids = client.post("/chunks", json=CHUNKS).json()["chunk_ids"]
    assert client.post("/embeddings/sync").json()["embedded"] == 4
    result = client.post("/search", json={"query": "fenced Markdown code blocks", "limit": 1}).json()["results"][0]
    assert result["id"] == ids[1]
    evaluation = client.post("/evaluate?k=1", json=[{"query": "HTTP timeout duplicate hashes", "relevant_chunk_ids": [ids[0]]}]).json()
    assert evaluation["recall_at_1"] == 1.0

