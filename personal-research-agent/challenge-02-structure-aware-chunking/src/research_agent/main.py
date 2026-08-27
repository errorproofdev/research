from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import httpx
import trafilatura
from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, HttpUrl

from .chunking import chunk_markdown
from .db import Database


class SourceCreate(BaseModel):
    url: HttpUrl


def create_app(db_path: str | Path | None = None, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    app = FastAPI(title="Personal Research Agent: Chunking")
    app.state.db = Database(db_path or os.getenv("RESEARCH_DB", "research.db"))
    app.state.transport = transport

    @app.post("/sources")
    async def create_source(payload: SourceCreate, request: Request, response: Response):
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10, headers={"User-Agent":"PersonalResearchAgent/0.2"}, transport=request.app.state.transport) as client:
                fetched = await client.get(str(payload.url))
                fetched.raise_for_status()
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "Source timed out") from exc
        except httpx.RequestError as exc:
            raise HTTPException(502, "Source could not be fetched") from exc
        media_type = fetched.headers.get("content-type", "").split(";", 1)[0].lower()
        if media_type not in {"text/html", "application/xhtml+xml"}:
            raise HTTPException(415, "Source is not HTML")
        content = trafilatura.extract(fetched.text, url=str(fetched.url), output_format="markdown", include_links=True, include_formatting=True)
        if not content:
            raise HTTPException(422, "No article body found")
        content = re.sub(r"\n{3,}", "\n\n", content.strip())
        metadata = trafilatura.extract_metadata(fetched.text, default_url=str(fetched.url))
        row, created = request.app.state.db.insert_source({"url":str(fetched.url),"title":metadata.title if metadata else None,"author":metadata.author if metadata else None,"published_at":metadata.date if metadata else None,"content":content,"content_hash":hashlib.sha256(content.encode()).hexdigest()})
        response.status_code = 201 if created else 200
        result = dict(row); result.pop("content"); result["created"] = created
        return result

    @app.post("/sources/{source_id}/chunks")
    def regenerate_chunks(source_id: int, request: Request):
        source = request.app.state.db.get_source(source_id)
        if not source:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
        rows = request.app.state.db.replace_chunks(source_id, chunk_markdown(source["content"]))
        return {"source_id": source_id, "count": len(rows), "chunks": [dict(row) for row in rows]}

    return app


app = create_app()

