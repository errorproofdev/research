from __future__ import annotations

import re

from .generators import DraftGenerator
from .models import ClaimAudit, DraftClaim, SourceChunk, SourceReference, SynthesisResult

TOKEN = re.compile(r"[a-z0-9]+")
NUMBER = re.compile(r"\b\d+(?:\.\d+)?%?\b")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "in",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "with",
}
REFUSAL = "I don't have enough supported evidence to answer that question."


def meaningful_tokens(text: str) -> set[str]:
    return {token for token in TOKEN.findall(text.lower()) if token not in STOPWORDS}


def audit_claim(claim_index: int, claim: DraftClaim, available: dict[int, SourceChunk], threshold: float) -> ClaimAudit:
    reasons = []
    if not claim.citations:
        reasons.append("missing_citation")
    unknown = sorted(set(claim.citations) - set(available))
    if unknown:
        reasons.append("unknown_citation")
    cited = [available[chunk_id] for chunk_id in dict.fromkeys(claim.citations) if chunk_id in available]
    evidence = " ".join(chunk.content for chunk in cited)
    claim_tokens = meaningful_tokens(claim.text)
    evidence_tokens = meaningful_tokens(evidence)
    support_score = len(claim_tokens & evidence_tokens) / max(1, len(claim_tokens))
    if support_score < threshold:
        reasons.append("insufficient_lexical_support")
    if not set(NUMBER.findall(claim.text)).issubset(set(NUMBER.findall(evidence))):
        reasons.append("unsupported_number")
    return ClaimAudit(
        claim_index=claim_index,
        supported=not reasons,
        support_score=round(support_score, 4),
        reasons=reasons,
        citations=claim.citations,
    )


class GroundedSynthesizer:
    def __init__(self, generator: DraftGenerator, support_threshold: float = 0.75):
        self.generator = generator
        self.support_threshold = support_threshold

    def synthesize(self, question: str, chunks: list[SourceChunk]) -> SynthesisResult:
        if not chunks:
            return SynthesisResult(refused=True, answer=REFUSAL, sources=[], audit=[])
        draft = self.generator.generate(question, chunks)
        available = {chunk.id: chunk for chunk in chunks}
        audit = [audit_claim(index, claim, available, self.support_threshold) for index, claim in enumerate(draft.claims)]
        if not draft.claims or any(not item.supported for item in audit):
            return SynthesisResult(refused=True, answer=REFUSAL, sources=[], audit=audit)

        cited_ids = list(dict.fromkeys(chunk_id for claim in draft.claims for chunk_id in claim.citations))
        labels = {chunk_id: f"S{index}" for index, chunk_id in enumerate(cited_ids, start=1)}
        sentences = []
        for claim in draft.claims:
            text = claim.text.strip()
            if text[-1] not in ".!?":
                text += "."
            citations = "".join(f"[{labels[chunk_id]}]" for chunk_id in dict.fromkeys(claim.citations))
            sentences.append(f"{text} {citations}")
        sources = [
            SourceReference(
                label=labels[chunk_id],
                chunk_id=chunk_id,
                source_id=available[chunk_id].source_id,
                title=available[chunk_id].title,
                url=available[chunk_id].url,
                heading_path=available[chunk_id].heading_path,
            )
            for chunk_id in cited_ids
        ]
        return SynthesisResult(refused=False, answer=" ".join(sentences), sources=sources, audit=audit)

