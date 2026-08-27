from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT,
    author TEXT,
    published_at TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def find_by_hash(self, content_hash: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM sources WHERE content_hash = ?", (content_hash,)
            ).fetchone()

    def insert_source(self, source: dict[str, str | None]) -> tuple[sqlite3.Row, bool]:
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM sources WHERE content_hash = ?",
                (source["content_hash"],),
            ).fetchone()
            if existing:
                return existing, False
            cursor = connection.execute(
                """
                INSERT INTO sources
                    (url, title, author, published_at, content, content_hash)
                VALUES (:url, :title, :author, :published_at, :content, :content_hash)
                """,
                source,
            )
            row = connection.execute(
                "SELECT * FROM sources WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            assert row is not None
            return row, True

