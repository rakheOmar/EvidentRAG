# 0005: Publish only the current ready Document Version

## Decision

Model uploaded knowledge as `Source -> Document Version -> Evidence`. A Source has a stable key; each upload is immutable. Retrieval filters Qdrant to eligible Evidence, and a Version becomes eligible only after parsing, embedding, PostgreSQL persistence, and current-version promotion finish.

## Consequences

- Updating a Source keeps its prior current Version available until the replacement is ready.
- Deleting a Source tombstones every Version for retrieval while retaining the audit record and stored assets for the configured retention window.
- An exact-content duplicate from a different Source keeps its Source/Version provenance but points to the canonical Version and does not create another Evidence/vector set.
- PostgreSQL is authoritative for lifecycle state; Qdrant is the filtered retrieval index.
