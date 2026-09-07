from __future__ import annotations

import base64
import binascii
import re

from .models import GatewayResult, SecurityEvent, SourceChunk

EXFIL_QUERY = re.compile(
    r"\b(?:show|reveal|print|return|dump|send|expose)\b.{0,60}"
    r"\b(?:system\s+prompt|developer\s+message|api[_ -]?key|secret|credential|environment\s+variable)s?\b",
    re.IGNORECASE | re.DOTALL,
)
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"(?:system|developer)\s+(?:prompt|message)\s*[:=]", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an|the)\b", re.IGNORECASE),
    re.compile(r"do\s+not\s+(?:answer|obey|follow)\s+(?:the\s+)?user", re.IGNORECASE),
    re.compile(r"(?:exfiltrate|upload|send)\b.{0,50}\b(?:secret|credential|token|environment)", re.IGNORECASE | re.DOTALL),
]
FAKE_CITATION = re.compile(r"\[(?:S|SOURCE)\s*\d+\]", re.IGNORECASE)
BASE64_CANDIDATE = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{32,}={0,2}(?![A-Za-z0-9+/=])")
SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(?:api[_ -]?key|password|secret|access[_ -]?token)\s*[:=]\s*[^\s,;]+"),
]


def has_direct_injection(text: str) -> bool:
    return any(pattern.search(text) for pattern in INJECTION_PATTERNS)


def has_encoded_injection(text: str) -> bool:
    for candidate in BASE64_CANDIDATE.findall(text):
        try:
            decoded = base64.b64decode(candidate, validate=True).decode("utf-8", "ignore")
        except (binascii.Error, ValueError):
            continue
        if has_direct_injection(decoded):
            return True
    return False


def redact_secrets(text: str) -> tuple[str, bool]:
    changed = False
    for pattern in SECRET_PATTERNS:
        text, count = pattern.subn("[REDACTED-SECRET]", text)
        changed |= bool(count)
    return text, changed


class EvidenceGateway:
    """Fail-closed policy between retrieval and answer generation."""

    def prepare(self, question: str, chunks: list[SourceChunk], tenant_id: str) -> GatewayResult:
        events: list[SecurityEvent] = []
        if EXFIL_QUERY.search(question):
            events.append(SecurityEvent(code="exfiltration_request", severity="critical", field="question"))
            return GatewayResult(refused=True, reason="unsafe_question", safe_chunks=[], events=events)

        safe_chunks: list[SourceChunk] = []
        for chunk in chunks:
            if chunk.tenant_id != tenant_id:
                events.append(SecurityEvent(code="foreign_tenant_evidence", severity="critical", chunk_id=chunk.id))
                continue

            metadata = f"{chunk.title}\n{chunk.heading_path}"
            if has_direct_injection(metadata) or has_encoded_injection(metadata):
                events.append(SecurityEvent(code="poisoned_metadata", severity="high", chunk_id=chunk.id, field="metadata"))
                continue
            if has_direct_injection(chunk.content):
                events.append(SecurityEvent(code="prompt_injection", severity="high", chunk_id=chunk.id, field="content"))
                continue
            if has_encoded_injection(chunk.content):
                events.append(SecurityEvent(code="encoded_prompt_injection", severity="high", chunk_id=chunk.id, field="content"))
                continue

            title, title_secret = redact_secrets(chunk.title)
            heading, heading_secret = redact_secrets(chunk.heading_path)
            content, content_secret = redact_secrets(chunk.content)
            if title_secret or heading_secret or content_secret:
                events.append(SecurityEvent(code="secret_redacted", severity="high", chunk_id=chunk.id))
            if FAKE_CITATION.search(content):
                content = FAKE_CITATION.sub("[UNTRUSTED-CITATION]", content)
                events.append(SecurityEvent(code="citation_laundering", severity="medium", chunk_id=chunk.id, field="content"))
            safe_chunks.append(chunk.model_copy(update={"title": title, "heading_path": heading, "content": content}))

        if not safe_chunks:
            return GatewayResult(refused=True, reason="no_safe_evidence", safe_chunks=[], events=events)
        return GatewayResult(refused=False, reason=None, safe_chunks=safe_chunks, events=events)

