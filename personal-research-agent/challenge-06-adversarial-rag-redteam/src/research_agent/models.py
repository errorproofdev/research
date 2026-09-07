from __future__ import annotations

from pydantic import BaseModel, Field


class SourceChunk(BaseModel):
    id: int
    source_id: int
    tenant_id: str
    title: str
    url: str
    heading_path: str = ""
    content: str = Field(min_length=1)


class SecurityEvent(BaseModel):
    code: str
    severity: str
    chunk_id: int | None = None
    field: str | None = None


class GatewayResult(BaseModel):
    refused: bool
    reason: str | None
    safe_chunks: list[SourceChunk]
    events: list[SecurityEvent]

