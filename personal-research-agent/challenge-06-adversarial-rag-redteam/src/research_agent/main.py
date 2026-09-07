from __future__ import annotations

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from .models import GatewayResult, SourceChunk
from .policy import EvidenceGateway


class PrepareInput(BaseModel):
    question: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    chunks: list[SourceChunk]


def create_app(gateway: EvidenceGateway | None = None) -> FastAPI:
    app = FastAPI(title="Personal Research Agent: Adversarial RAG Gateway")
    app.state.gateway = gateway or EvidenceGateway()

    @app.post("/security/prepare", response_model=GatewayResult)
    def prepare(payload: PrepareInput, request: Request):
        return request.app.state.gateway.prepare(payload.question, payload.chunks, payload.tenant_id)

    return app


app = create_app()

