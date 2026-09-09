from __future__ import annotations

from pydantic import BaseModel, Field


class FetchBudget(BaseModel):
    max_requests: int = Field(default=5, ge=1, le=20)
    max_redirects: int = Field(default=3, ge=0, le=10)
    max_total_bytes: int = Field(default=2_000_000, ge=1, le=20_000_000)
    timeout_seconds: float = Field(default=10.0, gt=0, le=60)


class TraceEntry(BaseModel):
    requested_url: str
    resolved_ips: list[str]
    connected_ip: str
    status_code: int
    location: str | None
    bytes_read: int
    sha256: str


class FetchResult(BaseModel):
    final_url: str
    status_code: int
    content_type: str | None
    body: bytes
    total_bytes: int
    trace: list[TraceEntry]


class FetchInput(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    allowed_domains: list[str] = Field(default_factory=list)
    budget: FetchBudget = Field(default_factory=FetchBudget)
