from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import SplitResult, urlsplit, urlunsplit


class FetchBlocked(ValueError):
    pass


class Resolver(Protocol):
    def resolve(self, hostname: str, port: int) -> list[str]: ...


class SystemResolver:
    def resolve(self, hostname: str, port: int) -> list[str]:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        }
        return sorted(addresses)


@dataclass(frozen=True)
class ValidatedTarget:
    url: str
    scheme: str
    hostname: str
    port: int
    request_target: str
    resolved_ips: tuple[str, ...]


class NetworkPolicy:
    def __init__(self, resolver: Resolver | None = None, allowed_domains: list[str] | None = None):
        self.resolver = resolver or SystemResolver()
        self.allowed_domains = tuple(self.normalize_hostname(item) for item in (allowed_domains or []))

    @staticmethod
    def normalize_hostname(hostname: str) -> str:
        try:
            return hostname.rstrip(".").encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise FetchBlocked("invalid_hostname") from exc

    def domain_allowed(self, hostname: str) -> bool:
        return not self.allowed_domains or any(
            hostname == domain or hostname.endswith("." + domain)
            for domain in self.allowed_domains
        )

    @staticmethod
    def validate_ip(value: str) -> str:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise FetchBlocked("invalid_ip") from exc
        if not address.is_global:
            raise FetchBlocked(f"non_public_ip:{address.compressed}")
        return address.compressed

    def validate(self, url: str) -> ValidatedTarget:
        if len(url) > 2048:
            raise FetchBlocked("url_too_long")
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise FetchBlocked("unsupported_scheme")
        if parsed.username is not None or parsed.password is not None:
            raise FetchBlocked("userinfo_forbidden")
        if not parsed.hostname:
            raise FetchBlocked("missing_hostname")
        hostname = self.normalize_hostname(parsed.hostname)
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise FetchBlocked("localhost_forbidden")
        if not self.domain_allowed(hostname):
            raise FetchBlocked("domain_not_allowed")
        try:
            port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        except ValueError as exc:
            raise FetchBlocked("invalid_port") from exc
        if port not in {80, 443}:
            raise FetchBlocked("port_not_allowed")

        # Validate every answer, not just the first. Mixed public/private DNS
        # results are rejected rather than leaving selection to another layer.
        raw_ips = self.resolver.resolve(hostname, port)
        if not raw_ips:
            raise FetchBlocked("dns_no_answers")
        resolved_ips = tuple(self.validate_ip(value) for value in raw_ips)
        path = parsed.path or "/"
        request_target = path + (f"?{parsed.query}" if parsed.query else "")
        netloc = hostname
        if port != (443 if parsed.scheme.lower() == "https" else 80):
            netloc += f":{port}"
        canonical = urlunsplit(SplitResult(parsed.scheme.lower(), netloc, path, parsed.query, ""))
        return ValidatedTarget(canonical, parsed.scheme.lower(), hostname, port, request_target, resolved_ips)
