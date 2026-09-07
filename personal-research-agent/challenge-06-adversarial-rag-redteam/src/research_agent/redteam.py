from __future__ import annotations

import json
from dataclasses import dataclass

from .models import SourceChunk
from .policy import EvidenceGateway


@dataclass(frozen=True)
class AttackCase:
    name: str
    question: str
    chunks: list[SourceChunk]
    tenant_id: str
    is_attack: bool
    expect_refused: bool
    expected_event_codes: frozenset[str] = frozenset()
    forbidden_substrings: tuple[str, ...] = ()


def run_redteam(gateway: EvidenceGateway, cases: list[AttackCase]) -> dict:
    if not cases:
        raise ValueError("Red-team suite cannot be empty")
    details = []
    attack_results, benign_results = [], []
    leaked_total = 0
    for case in cases:
        result = gateway.prepare(case.question, case.chunks, case.tenant_id)
        serialized = json.dumps([chunk.model_dump() for chunk in result.safe_chunks])
        codes = {event.code for event in result.events}
        leaked = [value for value in case.forbidden_substrings if value in serialized]
        passed = result.refused == case.expect_refused and case.expected_event_codes.issubset(codes) and not leaked
        leaked_total += bool(leaked)
        (attack_results if case.is_attack else benign_results).append(passed)
        details.append({
            "name": case.name,
            "passed": passed,
            "refused": result.refused,
            "event_codes": sorted(codes),
            "leaked": leaked,
        })
    return {
        "case_count": len(cases),
        "case_pass_rate": sum(item["passed"] for item in details) / len(cases),
        "attack_handled_rate": sum(attack_results) / max(1, len(attack_results)),
        "benign_pass_rate": sum(benign_results) / max(1, len(benign_results)),
        "secret_leak_rate": leaked_total / len(cases),
        "details": details,
    }

