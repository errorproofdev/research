from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .chunking import Chunk

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS sources (
 id INTEGER PRIMARY KEY, url TEXT NOT NULL, title TEXT, author TEXT, published_at TEXT,
 content TEXT NOT NULL, content_hash TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS chunks (
 id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
 chunk_index INTEGER NOT NULL, heading_path TEXT NOT NULL, content TEXT NOT NULL,
 token_count INTEGER NOT NULL, start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
 content_hash TEXT NOT NULL, oversized INTEGER NOT NULL DEFAULT 0,
 UNIQUE(source_id, chunk_index)
);
"""


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

    def insert_source(self, values: dict) -> tuple[sqlite3.Row, bool]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM sources WHERE content_hash=?", (values["content_hash"],)).fetchone()
            if row:
                return row, False
            cursor = db.execute("INSERT INTO sources(url,title,author,published_at,content,content_hash) VALUES(:url,:title,:author,:published_at,:content,:content_hash)", values)
            return db.execute("SELECT * FROM sources WHERE id=?", (cursor.lastrowid,)).fetchone(), True

    def get_source(self, source_id: int) -> sqlite3.Row | None:
        with self.connect() as db:
            return db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()

    def replace_chunks(self, source_id: int, chunks: list[Chunk]) -> list[sqlite3.Row]:
        with self.connect() as db:
            db.execute("DELETE FROM chunks WHERE source_id=?", (source_id,))
            db.executemany("""INSERT INTO chunks(source_id,chunk_index,heading_path,content,token_count,start_offset,end_offset,content_hash,oversized)
                VALUES(?,?,?,?,?,?,?,?,?)""", [(source_id,c.chunk_index,c.heading_path,c.content,c.token_count,c.start_offset,c.end_offset,c.content_hash,int(c.oversized)) for c in chunks])
            return db.execute("SELECT * FROM chunks WHERE source_id=? ORDER BY chunk_index", (source_id,)).fetchall()

