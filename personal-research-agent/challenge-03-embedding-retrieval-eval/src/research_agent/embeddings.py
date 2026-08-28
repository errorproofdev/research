from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    provider: str
    model: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector] if length else vector


@dataclass
class HashingEmbedder:
    """Deterministic, offline baseline for tests and lexical retrieval.

    It is intentionally not presented as a semantic model. Its purpose is to
    make the complete storage/evaluation loop reproducible before money or a
    network dependency is introduced.
    """

    dimension: int = 128
    provider: str = "local"
    model: str = "signed-feature-hash-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            words = TOKEN.findall(text.lower())
            features = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
            for feature in features:
                digest = hashlib.sha256(feature.encode()).digest()
                index = int.from_bytes(digest[:8], "big") % self.dimension
                vector[index] += 1.0 if digest[8] & 1 else -1.0
            results.append(normalize(vector))
        return results


class OpenAICompatibleEmbedder:
    """Adapter for hosted or local servers exposing `/v1/embeddings`."""

    provider = "openai-compatible"

    def __init__(
        self,
        model: str,
        dimension: int,
        base_url: str,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.model = model
        self.dimension = dimension
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.transport = transport

    def embed(self, texts: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        with httpx.Client(timeout=20, transport=self.transport) as client:
            response = client.post(
                f"{self.base_url}/v1/embeddings",
                headers=headers,
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda row: row["index"])
        return [row["embedding"] for row in rows]

