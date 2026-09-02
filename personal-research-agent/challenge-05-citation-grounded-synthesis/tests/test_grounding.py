from __future__ import annotations

import json

import httpx
from fastapi.testclient import TestClient

from research_agent.evaluation import SynthesisCase, evaluate
from research_agent.generators import ExtractiveGenerator, OpenAICompatibleJSONGenerator
from research_agent.grounding import GroundedSynthesizer
from research_agent.main import create_app
from research_agent.models import Draft, DraftClaim, SourceChunk

CHUNKS = [
    SourceChunk(id=10, source_id=1, title="SQLite Retrieval", url="https://example.test/sqlite", heading_path="FTS5", content="SQLite FTS5 provides BM25 keyword retrieval for identifiers and rare terms."),
    SourceChunk(id=11, source_id=2, title="Rank Fusion", url="https://example.test/rrf", heading_path="RRF", content="Reciprocal rank fusion combines lexical and dense rankings without normalizing their scores."),
]


class ScriptedGenerator:
    def __init__(self, claims):
        self.claims = claims

    def generate(self, question, chunks):
        return Draft(claims=self.claims)


def test_supported_claims_get_sentence_level_sources():
    generator = ScriptedGenerator([
        DraftClaim(text="SQLite FTS5 provides BM25 keyword retrieval.", citations=[10]),
        DraftClaim(text="Reciprocal rank fusion combines lexical and dense rankings.", citations=[11]),
    ])
    result = GroundedSynthesizer(generator).synthesize("How does retrieval work?", CHUNKS)
    assert result.refused is False
    assert result.answer.count("[S1]") == 1 and result.answer.count("[S2]") == 1
    assert [source.chunk_id for source in result.sources] == [10, 11]
    assert all(audit.supported for audit in result.audit)


def test_unsupported_number_refuses_entire_answer():
    generator = ScriptedGenerator([DraftClaim(text="SQLite FTS5 improves retrieval by 92 percent.", citations=[10])])
    result = GroundedSynthesizer(generator, support_threshold=0.5).synthesize("How much?", CHUNKS)
    assert result.refused is True
    assert "unsupported_number" in result.audit[0].reasons
    assert result.sources == []


def test_missing_and_unknown_citations_fail_closed():
    missing = GroundedSynthesizer(ScriptedGenerator([DraftClaim(text="SQLite provides retrieval.", citations=[])]))
    unknown = GroundedSynthesizer(ScriptedGenerator([DraftClaim(text="SQLite provides retrieval.", citations=[999])]))
    assert missing.synthesize("Question", CHUNKS).refused is True
    assert unknown.synthesize("Question", CHUNKS).refused is True


def test_empty_evidence_and_empty_draft_refuse():
    synthesizer = GroundedSynthesizer(ExtractiveGenerator())
    assert synthesizer.synthesize("Anything?", []).refused is True
    assert synthesizer.synthesize("unrelated vocabulary", CHUNKS).refused is True


def test_openai_compatible_adapter_uses_untrusted_evidence_contract():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert body["response_format"] == {"type": "json_object"}
        assert "untrusted evidence" in body["messages"][0]["content"]
        assert body["messages"][1]["role"] == "user"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"claims":[{"text":"SQLite FTS5 provides BM25 keyword retrieval.","citations":[10]}]}'}}]})

    adapter = OpenAICompatibleJSONGenerator("test-model", "https://model.test", transport=httpx.MockTransport(handler))
    draft = adapter.generate("What retrieves keywords?", CHUNKS)
    assert draft.claims[0].citations == [10]


def test_api_and_refusal_evaluation():
    client = TestClient(create_app())
    response = client.post("/synthesize", json={"question": "How does BM25 retrieve rare terms?", "chunks": [chunk.model_dump() for chunk in CHUNKS]})
    assert response.status_code == 200
    assert response.json()["refused"] is False
    synthesizer = GroundedSynthesizer(ScriptedGenerator([DraftClaim(text="Unsupported moon fact.", citations=[])]))
    report = evaluate(synthesizer, [SynthesisCase("Moon?", CHUNKS, True)])
    assert report["refusal_accuracy"] == 1.0

