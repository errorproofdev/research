from __future__ import annotations

import hashlib
from urllib.parse import urljoin

from .models import FetchBudget, FetchResult, TraceEntry
from .policy import FetchBlocked, NetworkPolicy
from .transport import PinnedSocketTransport, Transport

REDIRECTS = {301, 302, 303, 307, 308}


class BudgetExceeded(ValueError):
    pass


class SecureFetcher:
    def __init__(self, transport: Transport | None = None, resolver=None):
        self.transport = transport or PinnedSocketTransport()
        self.resolver = resolver

    def fetch(self, url: str, budget: FetchBudget | None = None, allowed_domains: list[str] | None = None) -> FetchResult:
        budget = budget or FetchBudget()
        policy = NetworkPolicy(self.resolver, allowed_domains)
        current_url = url
        trace: list[TraceEntry] = []
        total_bytes = 0
        redirects = 0

        while True:
            if len(trace) >= budget.max_requests:
                raise BudgetExceeded("request_budget_exceeded")
            target = policy.validate(current_url)
            remaining = budget.max_total_bytes - total_bytes
            if remaining <= 0:
                raise BudgetExceeded("byte_budget_exceeded")
            response = self.transport.request(target, budget.timeout_seconds, remaining)

            # The transport must connect to one of the exact validated answers.
            # This catches custom transports and DNS rebinding mistakes.
            connected_ip = policy.validate_ip(response.connected_ip)
            if connected_ip not in target.resolved_ips:
                raise FetchBlocked("peer_ip_not_validated")
            if len(response.body) > remaining:
                raise BudgetExceeded("byte_budget_exceeded")
            total_bytes += len(response.body)
            location = response.headers.get("location")
            trace.append(TraceEntry(
                requested_url=target.url,
                resolved_ips=list(target.resolved_ips),
                connected_ip=connected_ip,
                status_code=response.status_code,
                location=location,
                bytes_read=len(response.body),
                sha256=hashlib.sha256(response.body).hexdigest(),
            ))

            if response.status_code not in REDIRECTS:
                return FetchResult(
                    final_url=target.url,
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                    body=response.body,
                    total_bytes=total_bytes,
                    trace=trace,
                )
            if not location:
                raise FetchBlocked("redirect_without_location")
            if redirects >= budget.max_redirects:
                raise BudgetExceeded("redirect_budget_exceeded")
            next_url = urljoin(target.url, location)
            if target.scheme == "https" and next_url.lower().startswith("http://"):
                raise FetchBlocked("https_downgrade_forbidden")
            redirects += 1
            current_url = next_url
