from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from .embeddings import Embedder, HashingEmbedder
from .engine import HybridEngine
from .evaluation import EvaluationCase, evaluate
from .rerank import CoverageReranker, Reranker


class ChunkInput(BaseModel):
    source_id: int
    chunk_index: int
    heading_path: str = ""
    content: str = Field(min_length=1)


class SearchInput(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
    candidate_limit: int = Field(default=20, ge=1, le=200)
    rerank: bool = True


class EvaluationInput(BaseModel):
    query: str
    relevant_chunk_ids: list[int]


def create_app(db_path: str | Path | None = None, embedder: Embedder | None = None, reranker: Reranker | None = None) -> FastAPI:
    app = FastAPI(title="Personal Research Agent: Hybrid Retrieval")
    app.state.engine = HybridEngine(db_path or os.getenv("RESEARCH_DB", "research.db"), embedder or HashingEmbedder(), reranker or CoverageReranker())

    @app.post("/chunks")
    def upsert_chunks(chunks: list[ChunkInput], request: Request):
        return {"chunk_ids": request.app.state.engine.upsert_chunks([chunk.model_dump() for chunk in chunks])}

    @app.post("/index")
    def index(request: Request):
        return {"indexed": request.app.state.engine.index_vectors()}

    @app.post("/search")
    def search(payload: SearchInput, request: Request):
        return {"results": request.app.state.engine.search(payload.query, payload.limit, payload.candidate_limit, payload.rerank)}

    @app.post("/evaluate")
    def run_evaluation(cases: list[EvaluationInput], request: Request, k: int = 3):
        prepared = [EvaluationCase(case.query, frozenset(case.relevant_chunk_ids)) for case in cases]
        return evaluate(request.app.state.engine, prepared, k)

    return app


app = create_app()

