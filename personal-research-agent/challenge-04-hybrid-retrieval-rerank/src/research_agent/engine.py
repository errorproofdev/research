from __future__ import annotations

import math
import re
import sqlite3
import struct
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .embeddings import Embedder
from .rerank import Reranker

TOKEN = re.compile(r"[a-z0-9]+")
SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    heading_path TEXT NOT NULL,
    content TEXT NOT NULL,
    UNIQUE(source_id, chunk_index)
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED, heading_path, content, tokenize='porter unicode61'
);
CREATE TABLE IF NOT EXISTS vectors (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    vector BLOB NOT NULL
);
"""


def pack(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def unpack(blob: bytes, dimension: int) -> list[float]:
    return list(struct.unpack(f"<{dimension}f", blob))


def cosine(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


class HybridEngine:
    def __init__(self, path: str | Path, embedder: Embedder, reranker: Reranker):
        self.path = str(path)
        self.embedder = embedder
        self.reranker = reranker
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
        ids = []
        with self.connect() as db:
            for chunk in chunks:
                db.execute(
                    """INSERT INTO chunks(source_id,chunk_index,heading_path,content)
                    VALUES(?,?,?,?) ON CONFLICT(source_id,chunk_index) DO UPDATE SET
                    heading_path=excluded.heading_path,content=excluded.content""",
                    (chunk["source_id"], chunk["chunk_index"], chunk.get("heading_path", ""), chunk["content"]),
                )
                row = db.execute("SELECT * FROM chunks WHERE source_id=? AND chunk_index=?", (chunk["source_id"], chunk["chunk_index"])).fetchone()
                db.execute("DELETE FROM chunks_fts WHERE chunk_id=?", (row["id"],))
                db.execute("INSERT INTO chunks_fts(rowid,chunk_id,heading_path,content) VALUES(?,?,?,?)", (row["id"], row["id"], row["heading_path"], row["content"]))
                db.execute("DELETE FROM vectors WHERE chunk_id=?", (row["id"],))
                ids.append(row["id"])
        return ids

    def index_vectors(self) -> int:
        with self.connect() as db:
            rows = db.execute(
                """SELECT c.* FROM chunks c LEFT JOIN vectors v ON v.chunk_id=c.id
                WHERE v.chunk_id IS NULL OR v.model != ? ORDER BY c.id""",
                (self.embedder.model,),
            ).fetchall()
        if not rows:
            return 0
        vectors = self.embedder.embed([f"{row['heading_path']}\n{row['content']}" for row in rows])
        if len(vectors) != len(rows) or any(len(vector) != self.embedder.dimension for vector in vectors):
            raise ValueError("Embedding batch shape mismatch")
        with self.connect() as db:
            db.executemany(
                """INSERT INTO vectors(chunk_id,model,dimension,vector) VALUES(?,?,?,?)
                ON CONFLICT(chunk_id) DO UPDATE SET model=excluded.model,
                dimension=excluded.dimension,vector=excluded.vector""",
                [(row["id"], self.embedder.model, self.embedder.dimension, pack(vector)) for row, vector in zip(rows, vectors)],
            )
        return len(rows)

    def lexical_search(self, query: str, limit: int) -> list[dict]:
        tokens = TOKEN.findall(query.lower())
        if not tokens:
            return []
        # Construct MATCH from tokenized literals only; raw user syntax never
        # reaches FTS5, avoiding operators, quote errors, and column filters.
        match = " OR ".join(f'"{token}"' for token in dict.fromkeys(tokens))
        with self.connect() as db:
            rows = db.execute(
                """SELECT c.*,bm25(chunks_fts,0.0,2.0,1.0) AS bm25_score
                FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.chunk_id
                WHERE chunks_fts MATCH ? ORDER BY bm25_score ASC,c.id ASC LIMIT ?""",
                (match, limit),
            ).fetchall()
        return [{**dict(row), "lexical_score": -row["bm25_score"]} for row in rows]

    def dense_search(self, query: str, limit: int) -> list[dict]:
        query_vector = self.embedder.embed([query])[0]
        with self.connect() as db:
            rows = db.execute(
                """SELECT c.*,v.dimension,v.vector FROM chunks c JOIN vectors v
                ON v.chunk_id=c.id WHERE v.model=?""",
                (self.embedder.model,),
            ).fetchall()
        scored = [{**{key: row[key] for key in ("id", "source_id", "chunk_index", "heading_path", "content")}, "dense_score": cosine(query_vector, unpack(row["vector"], row["dimension"]))} for row in rows]
        return sorted(scored, key=lambda item: (-item["dense_score"], item["id"]))[:limit]

    def fuse(self, lexical: list[dict], dense: list[dict], rrf_k: int = 60) -> list[dict]:
        combined: dict[int, dict] = {}
        for channel, weight, rows in (("lexical", 1.2, lexical), ("dense", 1.0, dense)):
            for rank, row in enumerate(rows, start=1):
                item = combined.setdefault(row["id"], {**row, "fusion_score": 0.0, "lexical_rank": None, "dense_rank": None})
                item.update({key: value for key, value in row.items() if key.endswith("_score")})
                item[f"{channel}_rank"] = rank
                item["fusion_score"] += weight / (rrf_k + rank)
        return sorted(combined.values(), key=lambda item: (-item["fusion_score"], item["id"]))

    def search(self, query: str, limit: int = 5, candidate_limit: int = 20, rerank: bool = True) -> list[dict]:
        lexical = self.lexical_search(query, candidate_limit)
        dense = self.dense_search(query, candidate_limit)
        fused = self.fuse(lexical, dense)
        ranked = self.reranker.rerank(query, fused) if rerank else fused
        return ranked[:limit]

