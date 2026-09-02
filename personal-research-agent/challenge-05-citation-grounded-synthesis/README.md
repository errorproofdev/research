# Personal Research Agent — Challenge 5: Citation-grounded synthesis

A standalone, fail-closed answer boundary for the hybrid retrieval results produced in Challenge 4. Generators must return structured claims with retrieved chunk IDs; an independent verifier audits every claim before rendering sentence-level citations.

## Run it

```bash
uv sync --extra test
uv run pytest -q
uv run uvicorn research_agent.main:app --reload
```

Send `POST /synthesize` with a question and the reranked chunks. The response contains:

- `refused`: whether the evidence gate blocked the answer;
- `answer`: verified sentences with `[S1]`-style references;
- `sources`: stable labels mapped to title, URL, heading, source ID, and chunk ID;
- `audit`: claim-level support score and failure reasons.

## Guardrail contract

- Every factual sentence is represented as an individual structured claim.
- Every claim must cite at least one chunk from the supplied retrieval set.
- Meaningful claim tokens must meet the configured evidence-overlap threshold.
- Every number in a claim must occur in its cited evidence.
- Any missing, unknown, or unsupported citation refuses the entire answer.
- Citations are rendered only after verification, preventing a model from manufacturing trusted-looking source labels.

The offline extractive generator makes the complete loop deterministic. `OpenAICompatibleJSONGenerator` can call a hosted service or local runtime, but its output passes through the same verifier.

## Success contract

- Two supported claims produce two sentence-level source references.
- An invented `92 percent` claim is refused even when its other words overlap the evidence.
- Missing and out-of-scope citations fail closed.
- Empty retrieval and empty drafts refuse.
- The model adapter treats evidence as untrusted JSON and requires structured output.
- The refusal evaluation fixture achieves `refusal_accuracy = 1.0`.

Next: attack this boundary with poisoned source instructions, citation laundering, retrieval exfiltration attempts, and adversarially similar unsupported claims.
