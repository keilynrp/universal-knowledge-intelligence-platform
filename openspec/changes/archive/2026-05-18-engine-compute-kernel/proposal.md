## Why

The Rust engine (`ukip-engine`) currently only activates during data import — running graph materialization and text analysis pipelines, then sitting idle. Meanwhile, the Python backend performs CPU-intensive operations (authority resolution, topic modeling, correlation analysis, bulk disambiguation) in pure Python, which scales poorly as datasets grow. The pipeline framework, job system, and progress streaming infrastructure already exist in Rust but are underutilized. Evolving the engine from an import-only batch processor into a general-purpose compute kernel lets us offload CPU-bound work where Rust delivers 10-50x speedups, without rewriting the HTTP/auth/RBAC layer that Python handles well.

## What Changes

- **New compute pipelines** in the Rust engine for authority resolution (fuzzy matching, scoring, cross-source dedup), topic modeling (co-occurrence/PMI, clustering), correlation analysis (Cramer's V, chi-squared), bulk disambiguation (fuzzy string matching at scale), and normalization (unicode folding, diacritic stripping, rule application).
- **Scientific connectors pipeline** for fetching and parsing data from external APIs (OpenAlex, Crossref, PubMed) using Rust's async I/O.
- **Embedding generation pipeline** stub for future vector embedding computation.
- **Persistent job state** — migrate job tracking from in-memory `DashMap` to Postgres so the engine survives restarts.
- **Extended gRPC contract** — new proto messages for compute pipeline inputs/outputs beyond the current `Publication`-centric model.
- **Python backend delegation** — `EngineClient` gains methods for each new pipeline; Python analyzers become thin wrappers that delegate to the engine when available and fall back to local Python when it's not.

## Capabilities

### New Capabilities
- `compute-authority`: Authority resolution pipeline — fuzzy matching, weighted scoring engine, cross-source candidate deduplication in Rust.
- `compute-analytics`: Topic modeling (PMI co-occurrence, greedy clustering) and correlation analysis (Cramer's V) pipelines in Rust.
- `compute-disambiguation`: Bulk fuzzy string matching and token-sort-ratio disambiguation at scale in Rust.
- `compute-normalization`: Unicode normalization, diacritic stripping, and rule-based text normalization pipeline.
- `scientific-connectors`: Async Rust pipeline for fetching/parsing from OpenAlex, Crossref, PubMed APIs.
- `persistent-jobs`: Job state persistence in Postgres replacing the in-memory DashMap.
- `engine-proto-v2`: Extended gRPC protocol supporting compute pipeline inputs/outputs beyond publications.

### Modified Capabilities

## Impact

- **Engine crate** (`engine/`): New pipeline modules, updated proto definitions, job persistence layer, new dependencies (strsim, unicode-normalization already present, possibly reqwest for connectors).
- **Backend** (`backend/`): `EngineClient` extended with new RPC methods; `authority/`, `analyzers/`, enrichment worker updated to delegate to engine with Python fallback.
- **Proto** (`engine/proto/`): New message types for compute requests/responses; versioned as v2 alongside existing v1.
- **Database**: New table `engine_jobs` for persistent job state; engine writes to existing `raw_entities`, `authority_records`, analysis result columns.
- **Deployment**: Engine becomes a more critical service (no longer optional for performance); graceful degradation path preserved via Python fallback.
