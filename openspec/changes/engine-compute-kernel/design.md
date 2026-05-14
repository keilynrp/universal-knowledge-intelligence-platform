## Context

The Rust engine (`ukip-engine`) is a gRPC service built with tonic, backed by PostgreSQL via sqlx. It currently has two pipelines — `graph_materialization` and `text_analysis` — orchestrated through a `Pipeline` trait, a `PipelineRegistry`, and a `JobManager` with in-memory state. The Python FastAPI backend connects via `EngineClient` with graceful fallback when the engine is unavailable.

The Python backend currently owns CPU-intensive operations:
- `backend/authority/` — fuzzy matching with `token_sort_ratio`, weighted scoring engine, cross-source dedup via `ThreadPoolExecutor` (5 workers, 12s timeout)
- `backend/analyzers/topic_modeling.py` — PMI co-occurrence, greedy seed clustering over enrichment_concepts
- `backend/analyzers/correlation.py` — Cramer's V via numpy chi-squared
- Disambiguation — fuzzy string matching at scale across entity clusters
- Normalization — `backend/authority/normalize.py` with NFD diacritic stripping, `name_variants()`

These operations run in pure Python (or numpy) and become bottlenecks at scale. The Rust engine's pipeline framework is already designed for this kind of work but is currently import-only.

## Goals / Non-Goals

**Goals:**
- Extend the `Pipeline` trait to support compute workloads beyond import (analytics, resolution, disambiguation)
- Add new pipeline implementations that replicate Python's CPU-intensive logic in Rust
- Persist job state in Postgres so engine restarts don't lose tracking
- Extend the gRPC protocol with typed messages for each compute pipeline
- Maintain Python fallback — every pipeline delegation must degrade gracefully when the engine is unavailable
- Preserve the existing import pipelines unchanged

**Non-Goals:**
- Replacing FastAPI as the HTTP/auth/RBAC layer — Python keeps this role
- Replacing DuckDB for OLAP queries — it's already native C++ and fast
- Replacing ChromaDB for vector search — it's already native HNSW
- Building a real-time query engine — the engine remains batch-oriented
- Full embedding model inference in Rust — the stub pipeline will delegate to external services
- Multi-tenancy isolation beyond the existing `org_id` pattern

## Decisions

### 1. Generalized pipeline input via proto oneof

**Decision**: Extend `ProcessRequest` with a `oneof payload` field that carries pipeline-specific input alongside the existing `publications` field.

**Rationale**: The current `PipelineInput` assumes all pipelines consume `Vec<Publication>`. Compute pipelines need different inputs (entity IDs for disambiguation, field names for correlation, query terms for authority). A `oneof` in the proto keeps backward compatibility while allowing typed inputs per pipeline.

**Alternative considered**: Passing everything through `options: map<string, string>` — rejected because it loses type safety and makes the proto contract meaningless.

### 2. Pipeline categories via trait marker

**Decision**: Add a `fn category(&self) -> PipelineCategory` method to the `Pipeline` trait returning `Import` or `Compute`. Keep a single registry and job manager.

**Rationale**: Avoids duplicating infrastructure. The job manager, progress tracker, and gRPC service work identically regardless of pipeline category. The category marker is informational (health endpoint, UI display).

**Alternative considered**: Separate registries for import vs compute pipelines — rejected as unnecessary complexity with no functional benefit.

### 3. Persistent jobs via Postgres table

**Decision**: Add an `engine_jobs` table. `JobManager` writes state transitions to Postgres and keeps a hot cache in `DashMap` for active jobs. On startup, the engine marks any stale `running` jobs as `failed` (same pattern as the Python enrichment worker).

**Rationale**: In-memory-only state means engine restart = lost job history. As the engine handles more pipeline types, job persistence becomes critical for observability and retry logic.

**Alternative considered**: Redis for job state — rejected because Postgres is already a dependency and the write volume is low (job state transitions, not high-frequency events).

### 4. Fuzzy string matching via strsim crate

**Decision**: Use the `strsim` crate for Jaro-Winkler, Levenshtein, and sorted-token similarity. Implement `token_sort_ratio` as a custom function using `strsim::normalized_levenshtein` on sorted token sequences.

**Rationale**: `strsim` is battle-tested (50M+ downloads), zero-dependency, and covers all the algorithms currently used in `backend/authority/scoring.py`. The Python `fuzzywuzzy`/`thefuzz` library's `token_sort_ratio` is trivially reimplemented on top of it.

### 5. Scientific connectors use reqwest + tokio

**Decision**: Use `reqwest` for async HTTP and `serde_json` for response parsing. Each connector (OpenAlex, Crossref, PubMed) is a module under `pipelines/connectors/` implementing a `Connector` trait.

**Rationale**: Rust's async I/O with connection pooling and timeouts is more robust than Python's `aiohttp` for high-volume API fetching. Rate limiting and retry logic are baked into each connector module.

**Alternative considered**: Keeping connectors in Python since they're I/O-bound — valid, but parsing large JSON responses and extracting/normalizing fields is CPU-intensive enough to justify Rust, especially for bulk fetches.

### 6. Python fallback pattern

**Decision**: Each Python analyzer gains an `_try_engine()` method that calls `EngineClient.process_sync()` with the appropriate pipeline name. If the engine returns `None` (unavailable) or errors, the analyzer falls back to the existing pure-Python implementation. No behavioral change from the user's perspective.

**Rationale**: Preserves the current graceful degradation pattern established by the existing `EngineClient`. Users who don't run the engine get the same functionality, just slower.

## Risks / Trade-offs

**[Risk] Behavioral divergence between Rust and Python implementations** → Mitigation: Golden-file tests — run both implementations on the same input dataset and assert output equivalence within tolerance (fuzzy scores, keyword rankings). Part of CI.

**[Risk] Proto versioning complexity** → Mitigation: Use `oneof payload` extension rather than a separate v2 service. Existing clients continue working unchanged. New fields are additive.

**[Risk] Engine becomes a critical dependency** → Mitigation: Python fallback is mandatory for every delegated operation. Engine health is checked at startup; if unavailable, Python logs a warning and proceeds locally. No user-facing error.

**[Risk] Job table growth** → Mitigation: Add a `completed_at` timestamp and a periodic cleanup that archives jobs older than 7 days. Not in initial scope but designed for.

**[Risk] Connector rate limiting / API key management** → Mitigation: API keys passed via `options` map in `ProcessRequest`, never stored in engine config. Rate limiter state is per-connector, in-memory, reset on restart (acceptable for batch operations).

## Open Questions

- Should the embedding generation pipeline call an external API (OpenAI, local ollama) or is it purely a future placeholder?
- What's the priority order for compute pipelines? Recommendation: persistent-jobs first (infrastructure), then authority (highest CPU pain), then disambiguation, then analytics, then connectors.
- Should the engine expose a streaming results endpoint for long-running compute jobs (e.g., authority resolution producing candidates incrementally)?
