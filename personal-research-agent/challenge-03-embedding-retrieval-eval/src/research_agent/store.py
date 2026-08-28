from __future__ import annotations

import hashlib
import math
import sqlite3
import struct
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .embeddings import Embedder

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    heading_path TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    UNIQUE(source_id, chunk_index)
);
CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    vector BLOB NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY(chunk_id, provider, model)
);
"""


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def pack_vector(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def unpack_vector(blob: bytes, dimension: int) -> list[float]:
    return list(struct.unpack(f"<{dimension}f", blob))


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Vector dimensions do not match")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def upsert_chunks(self, chunks: list[dict]) -> list[int]:
        ids: list[int] = []
        with self.connect() as db:
            for chunk in chunks:
                digest = content_hash(chunk["content"])
                db.execute(
                    """INSERT INTO chunks(source_id,chunk_index,heading_path,content,content_hash)
                    VALUES(?,?,?,?,?) ON CONFLICT(source_id,chunk_index) DO UPDATE SET
                    heading_path=excluded.heading_path, content=excluded.content,
                    content_hash=excluded.content_hash""",
                    (chunk["source_id"], chunk["chunk_index"], chunk.get("heading_path", ""), chunk["content"], digest),
                )
                row = db.execute(
                    "SELECT id FROM chunks WHERE source_id=? AND chunk_index=?",
                    (chunk["source_id"], chunk["chunk_index"]),
                ).fetchone()
                ids.append(row["id"])
        return ids

    def sync_embeddings(self, embedder: Embedder) -> dict[str, int]:
        with self.connect() as db:
            pending = db.execute(
                """SELECT c.* FROM chunks c LEFT JOIN embeddings e
                ON e.chunk_id=c.id AND e.provider=? AND e.model=?
                WHERE e.chunk_id IS NULL OR e.content_hash != c.content_hash
                ORDER BY c.id""",
                (embedder.provider, embedder.model),
            ).fetchall()
        if not pending:
            return {"embedded": 0, "skipped": self.chunk_count()}

        vectors = embedder.embed([row["content"] for row in pending])
        if len(vectors) != len(pending):
            raise ValueError("Embedding provider returned the wrong row count")
        for vector in vectors:
            if len(vector) != embedder.dimension:
                raise ValueError("Embedding provider returned the wrong dimension")
            if not all(math.isfinite(value) for value in vector):
                raise ValueError("Embedding provider returned a non-finite value")

        # Validation happens before BEGIN IMMEDIATE, so a malformed batch writes
        # no partial vectors. The transaction then replaces the entire batch.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.executemany(
                """INSERT INTO embeddings(chunk_id,provider,model,dimension,vector,content_hash)
                VALUES(?,?,?,?,?,?) ON CONFLICT(chunk_id,provider,model) DO UPDATE SET
                dimension=excluded.dimension, vector=excluded.vector,
                content_hash=excluded.content_hash, created_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')""",
                [
                    (row["id"], embedder.provider, embedder.model, embedder.dimension, pack_vector(vector), row["content_hash"])
                    for row, vector in zip(pending, vectors)
                ],
            )
        return {"embedded": len(pending), "skipped": self.chunk_count() - len(pending)}

    def search(self, query: str, embedder: Embedder, limit: int = 5) -> list[dict]:
        query_vector = embedder.embed([query])[0]
        if len(query_vector) != embedder.dimension:
            raise ValueError("Query embedding has the wrong dimension")
        with self.connect() as db:
            rows = db.execute(
                """SELECT c.id,c.source_id,c.chunk_index,c.heading_path,c.content,
                e.dimension,e.vector FROM chunks c JOIN embeddings e ON e.chunk_id=c.id
                WHERE e.provider=? AND e.model=?""",
                (embedder.provider, embedder.model),
            ).fetchall()
        scored = [
            {**{key: row[key] for key in ("id", "source_id", "chunk_index", "heading_path", "content")}, "score": cosine(query_vector, unpack_vector(row["vector"], row["dimension"]))}
            for row in rows
        ]
        return sorted(scored, key=lambda row: (-row["score"], row["id"]))[:limit]

    def chunk_count(self) -> int:
        with self.connect() as db:
            return db.execute("SELECT count(*) FROM chunks").fetchone()[0]

