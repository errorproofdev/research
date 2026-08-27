from __future__ import annotations

import sqlite3

import httpx
from fastapi.testclient import TestClient

from research_agent.main import create_app

ARTICLE = """
<!doctype html><html><head><title>Reliable Retrieval</title>
<meta name="author" content="Ada Researcher">
<meta property="article:published_time" content="2026-08-20">
</head><body><nav>Home Products Pricing</nav><article>
<h1>Reliable Retrieval</h1><p>Dependable ingestion starts with a narrow boundary.</p>
<p>Content hashes identify duplicate articles across different URLs.</p>
</article><footer>Copyright and navigation clutter</footer></body></html>
"""


def client_for(tmp_path, handler):
    transport = httpx.MockTransport(handler)
    app = create_app(tmp_path / "test.db", transport=transport)
    return TestClient(app), tmp_path / "test.db"


def test_stores_once_and_deduplicates_across_urls(tmp_path):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=ARTICLE)

    client, db_path = client_for(tmp_path, handler)
    first = client.post("/sources", json={"url": "https://example.test/article"})
    second = client.post("/sources", json={"url": "https://mirror.test/same-article"})

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["created"] is True
    assert second.json()["created"] is False
    assert "content" not in first.json()
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT count(*) FROM sources").fetchone()[0] == 1
        content = connection.execute("SELECT content FROM sources").fetchone()[0]
    assert "Dependable ingestion" in content
    assert "Products Pricing" not in content


def test_rejects_bad_url_before_fetch(tmp_path):
    client, _ = client_for(tmp_path, lambda request: None)
    assert client.post("/sources", json={"url": "not a url"}).status_code == 422


def test_rejects_non_html(tmp_path):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")

    client, _ = client_for(tmp_path, handler)
    assert client.post("/sources", json={"url": "https://example.test/file.pdf"}).status_code == 415


def test_reports_timeout(tmp_path):
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    client, _ = client_for(tmp_path, handler)
    assert client.post("/sources", json={"url": "https://example.test/slow"}).status_code == 504


def test_reports_failed_extraction(tmp_path):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html></html>")

    client, _ = client_for(tmp_path, handler)
    assert client.post("/sources", json={"url": "https://example.test/empty"}).status_code == 422

