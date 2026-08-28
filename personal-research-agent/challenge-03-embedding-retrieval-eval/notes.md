# Working notes

- Inspected the two existing research-agent branches and their build logs before choosing the next roadmap step.
- Challenge 2 explicitly identified embedding chunks and measuring retrieval quality as the next skill.
- Added a deterministic signed feature-hashing baseline so the full pipeline can be tested offline without pretending it is a production semantic model.
- Added a separate OpenAI-compatible adapter so the storage and evaluation boundary does not depend on one hosted or local runtime.
- Store vectors as little-endian float32 blobs with provider, model, dimension, and source content hash metadata.
- Validate a whole provider batch before opening the write transaction so malformed output cannot partially update the index.
- Executed five deterministic tests covering idempotency, selective stale-row updates, quality floors, malformed-provider rollback, hosted-adapter ordering, and the API success loop. All passed.
