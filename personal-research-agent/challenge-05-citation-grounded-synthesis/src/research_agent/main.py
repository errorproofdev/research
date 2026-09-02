from __future__ import annotations

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from .generators import DraftGenerator, ExtractiveGenerator
from .grounding import GroundedSynthesizer
from .models import SourceChunk, SynthesisResult


class SynthesisInput(BaseModel):
    question: str = Field(min_length=1)
    chunks: list[SourceChunk]


def create_app(generator: DraftGenerator | None = None) -> FastAPI:
    app = FastAPI(title="Personal Research Agent: Grounded Synthesis")
    app.state.synthesizer = GroundedSynthesizer(generator or ExtractiveGenerator())

    @app.post("/synthesize", response_model=SynthesisResult)
    def synthesize(payload: SynthesisInput, request: Request):
        return request.app.state.synthesizer.synthesize(payload.question, payload.chunks)

    return app


app = create_app()

