from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from .embeddings import Embedder, HashingEmbedder
from .evaluation import EvaluationCase, evaluate_retrieval
from .store import Database


class ChunkInput(BaseModel):
    source_id: int
    chunk_index: int
    heading_path: str = ""
    content: str = Field(min_length=1)


class SearchInput(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


class EvaluationInput(BaseModel):
    query: str
    relevant_chunk_ids: list[int]


def create_app(db_path: str | Path | None = None, embedder: Embedder | None = None) -> FastAPI:
    app = FastAPI(title="Personal Research Agent: Retrieval Evaluation")
    app.state.db = Database(db_path or os.getenv("RESEARCH_DB", "research.db"))
    app.state.embedder = embedder or HashingEmbedder()

    @app.post("/chunks")
    def upsert_chunks(chunks: list[ChunkInput], request: Request):
        ids = request.app.state.db.upsert_chunks([chunk.model_dump() for chunk in chunks])
        return {"chunk_ids": ids}

    @app.post("/embeddings/sync")
    def sync_embeddings(request: Request):
        return request.app.state.db.sync_embeddings(request.app.state.embedder)

    @app.post("/search")
    def search(payload: SearchInput, request: Request):
        return {"results": request.app.state.db.search(payload.query, request.app.state.embedder, payload.limit)}

    @app.post("/evaluate")
    def evaluate(cases: list[EvaluationInput], request: Request, k: int = 3):
        evaluation_cases = [EvaluationCase(case.query, frozenset(case.relevant_chunk_ids)) for case in cases]
        return evaluate_retrieval(request.app.state.db, request.app.state.embedder, evaluation_cases, k)

    return app


app = create_app()

