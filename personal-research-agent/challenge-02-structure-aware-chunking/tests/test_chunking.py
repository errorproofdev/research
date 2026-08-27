from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from research_agent.chunking import chunk_markdown
from research_agent.main import create_app


def fixture() -> str:
    code = "\n".join(f"print('line {number}')" for number in range(100))
    oversized = " ".join(f"word{number}." for number in range(1800))
    repeated = "Retrieval quality must be measured against a labeled query set."
    return f"""# Retrieval

Introductory paragraph establishes the retrieval objective.

## Implementation

```python
{code}
```

{oversized}

### Evaluation

{repeated}

## Failure analysis

{repeated}
"""


def test_fixture_invariants():
    markdown = fixture()
    first = chunk_markdown(markdown, target_tokens=600, max_tokens=800, overlap_tokens=80)
    second = chunk_markdown(markdown, target_tokens=600, max_tokens=800, overlap_tokens=80)
    assert [c.chunk_index for c in first] == list(range(len(first)))
    assert [c.content_hash for c in first] == [c.content_hash for c in second]
    assert all(c.token_count <= 800 or c.oversized for c in first)
    code_chunks = [c for c in first if "print('line 0')" in c.content]
    assert len(code_chunks) == 1
    assert "print('line 99')" in code_chunks[0].content
    for paragraph in [p.strip() for p in markdown.split("\n\n") if p.strip() and not p.startswith("#")]:
        if paragraph.startswith("```python"):
            assert any(paragraph in c.content for c in first)
        elif len(paragraph.split()) < 1000:
            assert any(paragraph in c.content for c in first)


def test_oversized_code_is_preserved_and_marked():
    markdown = "# Code\n\n```text\n" + ("long_token " * 2000) + "\n```"
    chunks = chunk_markdown(markdown, target_tokens=60, max_tokens=80, overlap_tokens=10)
    assert len(chunks) == 1
    assert chunks[0].oversized is True
    assert chunks[0].content.count("```") == 2


def test_transactional_regeneration_is_deterministic(tmp_path):
    app = create_app(tmp_path / "test.db")
    with app.state.db.connect() as db:
        cursor = db.execute("INSERT INTO sources(url,content,content_hash) VALUES(?,?,?)", ("https://example.test", fixture(), "fixture-hash"))
        source_id = cursor.lastrowid
    client = TestClient(app)
    first = client.post(f"/sources/{source_id}/chunks")
    second = client.post(f"/sources/{source_id}/chunks")
    assert first.status_code == second.status_code == 200
    assert [c["content_hash"] for c in first.json()["chunks"]] == [c["content_hash"] for c in second.json()["chunks"]]
    assert first.json()["count"] == second.json()["count"]
    with sqlite3.connect(tmp_path / "test.db") as db:
        assert db.execute("SELECT count(*) FROM chunks").fetchone()[0] == first.json()["count"]
        hit = db.execute("SELECT chunk_index, heading_path FROM chunks WHERE content LIKE '%labeled query set%' ORDER BY chunk_index LIMIT 1").fetchone()
    assert hit is not None and "Evaluation" in hit[1]

