from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def arguments_hash(arguments: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(arguments).encode()).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class AuthorizationDenied(ValueError):
    pass


class ApprovalDenied(ValueError):
    pass


@dataclass(frozen=True)
class AuthorizationContext:
    subject: str
    scopes: frozenset[str]
    approval_token: str | None = None


class ApprovalAuthority:
    """Issues argument-bound, expiring, one-time approval tokens."""

    def __init__(
        self,
        secret: bytes,
        clock: Callable[[], float] = time.time,
        consumed_path: str | Path | None = None,
    ):
        if len(secret) < 32:
            raise ValueError("approval secret must contain at least 32 bytes")
        self.secret = secret
        self.clock = clock
        self.consumed_path = Path(consumed_path) if consumed_path else None
        self.consumed_nonces: set[str] = set()
        if self.consumed_path and self.consumed_path.exists():
            loaded = json.loads(self.consumed_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
                raise ValueError("invalid consumed approval ledger")
            self.consumed_nonces.update(loaded)

    def _persist_consumed(self) -> None:
        if not self.consumed_path:
            return
        self.consumed_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.consumed_path.with_suffix(self.consumed_path.suffix + ".tmp")
        temporary.write_text(canonical(sorted(self.consumed_nonces)), encoding="utf-8")
        temporary.replace(self.consumed_path)

    def issue(
        self,
        subject: str,
        tool: str,
        arguments: dict[str, Any],
        *,
        ttl_seconds: int = 300,
        nonce: str | None = None,
    ) -> str:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        claims = {
            "sub": subject,
            "tool": tool,
            "args_sha256": arguments_hash(arguments),
            "exp": int(self.clock()) + ttl_seconds,
            "nonce": nonce or secrets.token_urlsafe(18),
        }
        payload = _encode(canonical(claims).encode())
        signature = _encode(hmac.new(self.secret, payload.encode(), hashlib.sha256).digest())
        return f"{payload}.{signature}"

    def consume(
        self,
        token: str,
        subject: str,
        tool: str,
        arguments: dict[str, Any],
    ) -> None:
        try:
            payload, supplied_signature = token.split(".", 1)
            expected_signature = _encode(
                hmac.new(self.secret, payload.encode(), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ApprovalDenied("invalid_approval_signature")
            claims = json.loads(_decode(payload))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApprovalDenied("invalid_approval_token") from exc

        if int(self.clock()) >= claims.get("exp", 0):
            raise ApprovalDenied("approval_expired")
        if claims.get("sub") != subject or claims.get("tool") != tool:
            raise ApprovalDenied("approval_not_authorized_for_request")
        if claims.get("args_sha256") != arguments_hash(arguments):
            raise ApprovalDenied("approval_arguments_changed")
        nonce = claims.get("nonce")
        if not isinstance(nonce, str) or nonce in self.consumed_nonces:
            raise ApprovalDenied("approval_already_used")
        self.consumed_nonces.add(nonce)
        self._persist_consumed()
