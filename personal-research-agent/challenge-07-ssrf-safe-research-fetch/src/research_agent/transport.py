from __future__ import annotations

import http.client
import socket
import ssl
from dataclasses import dataclass
from typing import Protocol

from .policy import ValidatedTarget


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes
    connected_ip: str


class Transport(Protocol):
    def request(self, target: ValidatedTarget, timeout: float, max_bytes: int) -> TransportResponse: ...


class PinnedSocketTransport:
    """Connects to a validated IP while retaining HTTP Host and TLS SNI."""

    def __init__(self, ssl_context: ssl.SSLContext | None = None):
        self.ssl_context = ssl_context or ssl.create_default_context()

    def request(self, target: ValidatedTarget, timeout: float, max_bytes: int) -> TransportResponse:
        selected_ip = target.resolved_ips[0]
        raw_socket = socket.create_connection((selected_ip, target.port), timeout=timeout)
        connection: http.client.HTTPConnection | None = None
        try:
            if target.scheme == "https":
                tls_socket = self.ssl_context.wrap_socket(raw_socket, server_hostname=target.hostname)
                connection = http.client.HTTPSConnection(target.hostname, target.port, timeout=timeout, context=self.ssl_context)
                connection.sock = tls_socket
            else:
                connection = http.client.HTTPConnection(target.hostname, target.port, timeout=timeout)
                connection.sock = raw_socket
            connected_ip = connection.sock.getpeername()[0]
            connection.request(
                "GET",
                target.request_target,
                headers={
                    "Host": target.hostname,
                    "User-Agent": "PersonalResearchAgent/0.7",
                    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8",
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            body = response.read(max_bytes + 1)
            headers = {name.lower(): value for name, value in response.getheaders()}
            return TransportResponse(response.status, headers, body, connected_ip)
        finally:
            if connection is not None:
                connection.close()
            else:
                raw_socket.close()
