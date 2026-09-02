from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Protocol

TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dimension: int
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class HashingEmbedder:
    """Deterministic offline dense baseline, not a semantic-model substitute."""

    dimension: int = 256
    model: str = "signed-feature-hash-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        output = []
        for text in texts:
            vector = [0.0] * self.dimension
            words = TOKEN.findall(text.lower())
            features = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
            for feature in features:
                digest = hashlib.sha256(feature.encode()).digest()
                vector[int.from_bytes(digest[:8], "big") % self.dimension] += 1 if digest[8] & 1 else -1
            norm = math.sqrt(sum(value * value for value in vector))
            output.append([value / norm for value in vector] if norm else vector)
        return output

