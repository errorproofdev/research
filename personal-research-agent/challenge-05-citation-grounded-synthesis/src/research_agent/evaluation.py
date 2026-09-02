from __future__ import annotations

from dataclasses import dataclass

from .grounding import GroundedSynthesizer
from .models import SourceChunk


@dataclass(frozen=True)
class SynthesisCase:
    question: str
    chunks: list[SourceChunk]
    expect_refusal: bool


def evaluate(synthesizer: GroundedSynthesizer, cases: list[SynthesisCase]) -> dict:
    if not cases:
        raise ValueError("Evaluation set cannot be empty")
    results = [synthesizer.synthesize(case.question, case.chunks) for case in cases]
    audits = [audit for result in results for audit in result.audit]
    return {
        "case_count": len(cases),
        "refusal_accuracy": sum(result.refused == case.expect_refusal for result, case in zip(results, cases)) / len(cases),
        "citation_coverage": sum(bool(audit.citations) for audit in audits) / max(1, len(audits)),
        "claim_support_rate": sum(audit.supported for audit in audits) / max(1, len(audits)),
        "details": [{"question": case.question, "expected_refusal": case.expect_refusal, "actual_refusal": result.refused} for case, result in zip(cases, results)],
    }

