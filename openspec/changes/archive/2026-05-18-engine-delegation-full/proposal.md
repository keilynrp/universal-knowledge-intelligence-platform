## Why

The `engine-compute-kernel` change delivered 6 Rust compute pipelines and Python `EngineClient` convenience methods (`process_analytics`, `process_disambiguation`, `process_normalization`, `process_connectors`), but only the authority resolution router was wired for engine delegation (task 9.2). The analytics, disambiguation, normalization, and connector endpoints still run pure Python — missing the 10-50x speedup the Rust engine provides on large datasets. Completing the delegation layer is the critical last mile to realize the performance investment.

## What Changes

- Wire the 4 analytics endpoints (`/analyzers/topics`, `/cooccurrence`, `/clusters`, `/correlation`) to delegate to the Rust `compute_analytics` pipeline when the engine is available, falling back to Python `TopicAnalyzer` / `CorrelationAnalyzer`.
- Wire the disambiguation endpoint (`/disambiguate/{field}`) to delegate to the Rust `compute_disambiguation` pipeline for datasets above a configurable threshold (default: 100 values), falling back to Python `_build_disambig_groups`.
- Wire normalization rule application (`/rules/apply`) to batch-delegate bulk value normalization to the Rust `compute_normalization` pipeline when processing > 100 values.
- Wire scientific connector endpoints to optionally delegate fetches to the Rust `compute_connectors` pipeline, with fallback to existing Python import adapters.
- Add a shared delegation helper to reduce boilerplate across routers.
- Add integration tests verifying delegation and fallback for each pipeline.

## Capabilities

### New Capabilities
- `analytics-delegation`: Delegate topic, cooccurrence, cluster, and correlation analytics to the Rust engine with transparent fallback
- `disambiguation-delegation`: Delegate fuzzy disambiguation to the Rust engine for large value sets with transparent fallback
- `normalization-delegation`: Batch-delegate normalization rule application to the Rust engine with transparent fallback
- `connector-delegation`: Delegate scientific API fetches (OpenAlex, Crossref, PubMed) to the Rust engine with transparent fallback

### Modified Capabilities
_(none — no existing spec-level requirements change, only implementation routing)_

## Impact

- **Backend routers**: `analytics.py`, `disambiguation.py`, `harmonization.py`, ingest connector paths
- **New module**: `backend/services/engine_delegation.py` — shared try-engine-or-fallback helper
- **Tests**: New test files for each delegation path (mock engine responses + fallback verification)
- **No frontend changes**: delegation is transparent to the API contract
- **No proto changes**: all needed proto messages already exist from `engine-compute-kernel`
- **No Rust changes**: all pipelines already implemented and tested
