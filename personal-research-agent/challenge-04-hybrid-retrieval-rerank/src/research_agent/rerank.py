from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

TOKEN = re.compile(r"[a-z0-9]+")


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[dict]) -> list[dict]: ...


@dataclass
class CoverageReranker:
    """Auditable offline baseline behind a replaceable reranker interface."""

    fusion_weight: float = 0.25

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        query_tokens = set(TOKEN.findall(query.lower()))
        ranked = []
        for candidate in candidates:
            content_tokens = set(TOKEN.findall(candidate["content"].lower()))
            heading_tokens = set(TOKEN.findall(candidate["heading_path"].lower()))
            coverage = len(query_tokens & content_tokens) / max(1, len(query_tokens))
            heading_coverage = len(query_tokens & heading_tokens) / max(1, len(query_tokens))
            phrase = float(query.lower() in candidate["content"].lower())
            score = coverage + 0.35 * heading_coverage + 0.2 * phrase + self.fusion_weight * candidate["fusion_score"]
            ranked.append({**candidate, "rerank_score": score})
        return sorted(ranked, key=lambda item: (-item["rerank_score"], item["id"]))

