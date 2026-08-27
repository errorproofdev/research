from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Annotated

import httpx
import trafilatura
from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, HttpUrl

from .db import Database

USER_AGENT = "PersonalResearchAgent/0.1 (+https://github.com/errorproofdev/research)"


class SourceCreate(BaseModel):
    url: HttpUrl


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    title: str | None
    author: str | None
    published_at: str | None
    content_hash: str
    created_at: str
    created: bool


def normalize_content(content: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", content.strip())


def create_app(
    db_path: str | Path | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    app = FastAPI(title="Personal Research Agent: Ingestion")
    app.state.db = Database(db_path or os.getenv("RESEARCH_DB", "research.db"))
    app.state.transport = transport

    @app.post("/sources", response_model=SourceResponse)
    async def create_source(payload: SourceCreate, request: Request, response: Response):
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": USER_AGENT},
                transport=request.app.state.transport,
            ) as client:
                fetched = await client.get(str(payload.url))
                fetched.raise_for_status()
        except httpx.TimeoutException as exc:
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "Source timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                f"Source returned HTTP {exc.response.status_code}",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Source could not be fetched") from exc

        media_type = fetched.headers.get("content-type", "").split(";", 1)[0].lower()
        if media_type not in {"text/html", "application/xhtml+xml"}:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Source is not HTML")

        content = trafilatura.extract(
            fetched.text,
            url=str(fetched.url),
            output_format="markdown",
            include_links=True,
            include_formatting=True,
        )
        if not content or not content.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No article body found")

        metadata = trafilatura.extract_metadata(fetched.text, default_url=str(fetched.url))
        normalized = normalize_content(content)
        source = {
            "url": str(fetched.url),
            "title": metadata.title if metadata else None,
            "author": metadata.author if metadata else None,
            "published_at": metadata.date if metadata else None,
            "content": normalized,
            "content_hash": hashlib.sha256(normalized.encode()).hexdigest(),
        }
        row, created = request.app.state.db.insert_source(source)
        response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return SourceResponse(**dict(row), created=created)

    return app


app = create_app()

