from __future__ import annotations

from pydantic import BaseModel, Field


class SourceChunk(BaseModel):
    id: int
    source_id: int
    title: str
    url: str
    heading_path: str = ""
    content: str = Field(min_length=1)


class DraftClaim(BaseModel):
    text: str = Field(min_length=1)
    citations: list[int]


class Draft(BaseModel):
    claims: list[DraftClaim]


class ClaimAudit(BaseModel):
    claim_index: int
    supported: bool
    support_score: float
    reasons: list[str]
    citations: list[int]


class SourceReference(BaseModel):
    label: str
    chunk_id: int
    source_id: int
    title: str
    url: str
    heading_path: str


class SynthesisResult(BaseModel):
    refused: bool
    answer: str
    sources: list[SourceReference]
    audit: list[ClaimAudit]

