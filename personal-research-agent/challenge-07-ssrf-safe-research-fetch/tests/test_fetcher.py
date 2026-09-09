from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from research_agent.fetcher import BudgetExceeded, SecureFetcher
from research_agent.main import create_app
from research_agent.models import FetchBudget
from research_agent.policy import FetchBlocked
from research_agent.transport import TransportResponse

PUBLIC_A = "93.184.216.34"
PUBLIC_B = "142.250.72.14"


class FakeResolver:
    def __init__(self, records):
        self.records = records

    def resolve(self, hostname, port):
        return self.records.get(hostname, [hostname])


class FakeTransport:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def request(self, target, timeout, max_bytes):
        self.calls.append((target.url, target.resolved_ips, max_bytes))
        status, headers, body, peer = self.routes[target.url]
        return TransportResponse(status, headers, body, peer)


def make_fetcher(records, routes):
    return SecureFetcher(FakeTransport(routes), FakeResolver(records))


@pytest.mark.parametrize("url,records", [
    ("http://127.0.0.1/admin", {}),
    ("http://169.254.169.254/latest/meta-data", {}),
    ("http://[::1]/", {}),
    ("https://internal.test/", {"internal.test": ["10.0.0.5"]}),
    ("https://mixed.test/", {"mixed.test": [PUBLIC_A, "192.168.1.2"]}),
])
def test_non_public_targets_are_blocked(url, records):
    with pytest.raises(FetchBlocked, match="non_public_ip"):
        make_fetcher(records, {}).fetch(url)


def test_allowlist_uses_domain_boundaries():
    fetcher = make_fetcher({"example.com.evil.test": [PUBLIC_A]}, {})
    with pytest.raises(FetchBlocked, match="domain_not_allowed"):
        fetcher.fetch("https://example.com.evil.test/", allowed_domains=["example.com"])


def test_redirect_target_is_revalidated_before_second_request():
    transport = FakeTransport({"https://start.test/": (302, {"location": "https://169.254.169.254/metadata"}, b"", PUBLIC_A)})
    fetcher = SecureFetcher(transport, FakeResolver({"start.test": [PUBLIC_A]}))
    with pytest.raises(FetchBlocked, match="non_public_ip"):
        fetcher.fetch("https://start.test/")
    assert len(transport.calls) == 1


def test_peer_must_match_validated_dns_answer():
    fetcher = make_fetcher(
        {"rebind.test": [PUBLIC_A]},
        {"https://rebind.test/": (200, {"content-type": "text/plain"}, b"data", PUBLIC_B)},
    )
    with pytest.raises(FetchBlocked, match="peer_ip_not_validated"):
        fetcher.fetch("https://rebind.test/")


def test_byte_and_redirect_budgets_fail_closed():
    large = make_fetcher({"large.test": [PUBLIC_A]}, {"https://large.test/": (200, {}, b"123456", PUBLIC_A)})
    with pytest.raises(BudgetExceeded, match="byte_budget"):
        large.fetch("https://large.test/", FetchBudget(max_total_bytes=5))
    looping = make_fetcher(
        {"loop.test": [PUBLIC_A]},
        {"https://loop.test/": (302, {"location": "/"}, b"", PUBLIC_A)},
    )
    with pytest.raises(BudgetExceeded, match="redirect_budget"):
        looping.fetch("https://loop.test/", FetchBudget(max_redirects=1))


def test_successful_redirect_has_auditable_provenance():
    routes = {
        "https://start.test/article": (302, {"location": "https://docs.test/final"}, b"move", PUBLIC_A),
        "https://docs.test/final": (200, {"content-type": "text/html"}, b"<p>evidence</p>", PUBLIC_B),
    }
    fetcher = make_fetcher({"start.test": [PUBLIC_A], "docs.test": [PUBLIC_B]}, routes)
    result = fetcher.fetch("https://start.test/article", allowed_domains=["start.test", "docs.test"])
    assert result.final_url == "https://docs.test/final"
    assert result.total_bytes == len(b"move<p>evidence</p>")
    assert [entry.connected_ip for entry in result.trace] == [PUBLIC_A, PUBLIC_B]
    assert result.trace[1].sha256 == hashlib.sha256(b"<p>evidence</p>").hexdigest()


def test_https_downgrade_is_forbidden():
    fetcher = make_fetcher(
        {"secure.test": [PUBLIC_A], "plain.test": [PUBLIC_B]},
        {"https://secure.test/": (302, {"location": "http://plain.test/"}, b"", PUBLIC_A)},
    )
    with pytest.raises(FetchBlocked, match="https_downgrade"):
        fetcher.fetch("https://secure.test/")


def test_api_success_and_blocked_statuses():
    fetcher = make_fetcher(
        {"docs.test": [PUBLIC_A]},
        {"https://docs.test/": (200, {"content-type": "text/plain"}, b"safe", PUBLIC_A)},
    )
    client = TestClient(create_app(fetcher))
    ok = client.post("/research/fetch", json={"url": "https://docs.test/", "allowed_domains": ["docs.test"]})
    assert ok.status_code == 200 and ok.json()["total_bytes"] == 4
    blocked = client.post("/research/fetch", json={"url": "http://127.0.0.1/"})
    assert blocked.status_code == 422
