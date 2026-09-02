# Working notes

- Inspected the remote Challenge 4 branch and build log before selecting this task.
- Challenge 4 explicitly handed off to citation-grounded synthesis with unsupported-claim refusal.
- Require generators to return structured claims and chunk IDs rather than parsing citations out of prose after generation.
- Separate generation from verification so the same guardrail applies to offline, hosted, and local model runtimes.
- Check citation presence, citation scope, meaningful-token support, and numeric support independently.
- Fail closed for the whole answer if any factual claim fails; do not quietly return a mixture of verified and unverified prose.
- Render citations only after verification, using stable source labels and sentence-level references.
- Executed six deterministic tests covering supported multi-source synthesis, numeric hallucination, missing and unknown citations, empty evidence, the hosted/local adapter contract, the API path, and refusal accuracy. All passed.
