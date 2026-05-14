## 1. Infrastructure: Persistent Jobs

- [x] 1.1 Create `engine_jobs` Postgres table migration in engine startup (id UUID PK, job_id TEXT UNIQUE, pipeline TEXT, status TEXT, progress REAL, result_json TEXT NULL, error TEXT NULL, created_at TIMESTAMPTZ, started_at TIMESTAMPTZ NULL, completed_at TIMESTAMPTZ NULL)
- [x] 1.2 Add sqlx queries for job CRUD: insert_job, update_status, update_completed, update_failed, find_by_job_id, list_jobs (with pipeline/status filters, limit, order by created_at desc)
- [x] 1.3 Refactor `JobManager` to write state transitions to Postgres while keeping DashMap as hot cache for active jobs
- [x] 1.4 Add startup recovery: UPDATE engine_jobs SET status='failed', error='engine restarted' WHERE status IN ('running', 'queued')
- [x] 1.5 Implement `ListJobs` gRPC endpoint with `ListJobsRequest`/`ListJobsResponse` proto messages
- [x] 1.6 Add cache eviction: remove completed/failed jobs from DashMap after 60s, falling back to Postgres on `GetJobStatus`
- [x] 1.7 Write tests for job persistence, startup recovery, cache eviction, and ListJobs

## 2. Proto Extensions (engine-proto-v2)

- [x] 2.1 Add `oneof payload` to `ProcessRequest` with typed message fields: AuthorityRequest, AnalyticsRequest, DisambiguationRequest, NormalizationRequest, ConnectorRequest
- [x] 2.2 Define `AuthorityRequest` and `AuthorityResponse` (AuthorityCandidateGroup, AuthorityCandidate) proto messages
- [x] 2.3 Define `AnalyticsRequest` and `AnalyticsResponse` (TopicEntry, CooccurrencePair, TopicCluster, CorrelationPair) proto messages
- [x] 2.4 Define `DisambiguationRequest` and `DisambiguationResponse` (DisambiguationCluster with canonical_value, variants, scores) proto messages
- [x] 2.5 Define `NormalizationRequest` (with NormalizationRule) and `NormalizationResponse` proto messages
- [x] 2.6 Define `ConnectorRequest` and `ConnectorResponse` proto messages
- [x] 2.7 Add `ListJobsRequest`/`ListJobsResponse`/`JobSummary` proto messages
- [x] 2.8 Update `ProcessResponse` with an extended result field (oneof or bytes) for typed pipeline responses
- [x] 2.9 Regenerate Rust proto bindings, verify existing import pipelines still compile and work unchanged
- [x] 2.10 Regenerate Python proto bindings, verify existing EngineClient still works

## 3. Pipeline Framework Extension

- [x] 3.1 Add `PipelineCategory` enum (Import, Compute) and `fn category(&self) -> PipelineCategory` to Pipeline trait with default `Import`
- [x] 3.2 Update `PipelineInput` to carry an optional typed payload (deserialized from proto oneof) alongside the existing publications vec
- [x] 3.3 Update `EngineService::process_sync` and `process_async` to deserialize oneof payload and pass it through PipelineInput
- [x] 3.4 Update health endpoint to report pipelines grouped by category
- [x] 3.5 Write tests for pipeline dispatch with both import and compute payloads

## 4. Compute Pipeline: Authority Resolution

- [x] 4.1 Create `engine/src/pipelines/authority/mod.rs` with `AuthorityPipeline` implementing Pipeline trait (category=Compute)
- [x] 4.2 Implement fuzzy string matching module (`authority/fuzzy.rs`): Jaro-Winkler via strsim, token-sort-ratio (sorted token normalized Levenshtein)
- [x] 4.3 Implement NFD diacritic normalization and ASCII folding (`authority/normalize.rs`) using unicode-normalization crate
- [x] 4.4 Implement name variant generation (full, surname-first, initials-only, first-last)
- [x] 4.5 Implement weighted scoring engine (`authority/scoring.rs`): 0.35/0.25/0.20/0.10/0.10 weights, dynamic renormalization for missing context
- [x] 4.6 Implement resolution status thresholds: exact_match >= 0.85, probable_match >= 0.65, ambiguous >= 0.45, unresolved < 0.45
- [x] 4.7 Implement cross-source candidate deduplication (token-sort-ratio >= 92 merge threshold, merged_sources tracking)
- [x] 4.8 Register AuthorityPipeline in main.rs PipelineRegistry
- [x] 4.9 Add `strsim` dependency to Cargo.toml
- [x] 4.10 Write unit tests for fuzzy matching, scoring, dedup, and end-to-end pipeline
- [x] 4.11 Write golden-file test comparing Rust output vs Python output on a reference dataset

## 5. Compute Pipeline: Analytics (Topics + Correlation)

- [x] 5.1 Create `engine/src/pipelines/analytics/mod.rs` with `AnalyticsPipeline` implementing Pipeline trait
- [x] 5.2 Implement topic extraction: query enrichment_concepts from DB, split by comma, count frequencies, return top N
- [x] 5.3 Implement PMI co-occurrence: compute pointwise mutual information for concept pairs
- [x] 5.4 Implement greedy topic clustering: seed by highest-frequency concept, assign co-occurring concepts
- [x] 5.5 Implement Cramer's V correlation: chi-squared computation over categorical fields, cardinality guard (max 50), skip-field list
- [x] 5.6 Register AnalyticsPipeline in main.rs
- [x] 5.7 Write tests for topics, PMI, clustering, and correlation
- [x] 5.8 Write golden-file test vs Python TopicAnalyzer and CorrelationAnalyzer

## 6. Compute Pipeline: Disambiguation

- [x] 6.1 Create `engine/src/pipelines/disambiguation/mod.rs` with `DisambiguationPipeline`
- [x] 6.2 Implement sorted-neighborhood blocking for candidate pair generation (avoid O(n^2))
- [x] 6.3 Implement fuzzy clustering: group values by token-sort-ratio >= threshold, pick canonical by frequency/length
- [x] 6.4 Register DisambiguationPipeline in main.rs
- [x] 6.5 Write tests including a 10k+ value performance test (must complete < 30s)

## 7. Compute Pipeline: Normalization

- [x] 7.1 Create `engine/src/pipelines/normalization/mod.rs` with `NormalizationPipeline`
- [x] 7.2 Implement unicode normalization mode (NFD + combining character removal + ASCII folding)
- [x] 7.3 Implement name_variants mode (reuse authority/normalize.rs)
- [x] 7.4 Implement rules mode: apply regex pattern/replacement rules in order
- [x] 7.5 Add `regex` (already a dependency) for rule application
- [x] 7.6 Register NormalizationPipeline in main.rs
- [x] 7.7 Write tests for each normalization mode

## 8. Scientific Connectors Pipeline

- [x] 8.1 Create `engine/src/pipelines/connectors/mod.rs` with `ConnectorPipeline` and `Connector` trait
- [x] 8.2 Implement OpenAlex connector module (reqwest async, JSON parsing, Publication mapping)
- [x] 8.3 Implement Crossref connector module (DOI resolution, metadata extraction)
- [x] 8.4 Implement PubMed connector module (E-utilities API, XML/JSON parsing)
- [x] 8.5 Implement shared rate limiter (token bucket, per-source, process-level via Arc)
- [x] 8.6 Implement retry logic with exponential backoff (3 retries, 1s/2s/4s) for transient errors (429, 503)
- [x] 8.7 Add `reqwest` dependency to Cargo.toml with rustls-tls feature
- [x] 8.8 Register ConnectorPipeline in main.rs
- [x] 8.9 Write unit tests with mock HTTP responses
- [x] 8.10 Write integration test (behind feature flag) against live APIs

## 9. Python Backend Delegation

- [x] 9.1 Extend `EngineClient` with `process_authority()`, `process_analytics()`, `process_disambiguation()`, `process_normalization()`, `process_connectors()` convenience methods
- [x] 9.2 Update `backend/authority/resolver.py` to try engine delegation with fallback
- [x] 9.3 Update `backend/analyzers/topic_modeling.py` to try engine delegation with fallback
- [x] 9.4 Update `backend/analyzers/correlation.py` to try engine delegation with fallback
- [x] 9.5 Update disambiguation endpoint to try engine delegation with fallback
- [x] 9.6 Update normalization calls to batch-delegate to engine for bulk operations (>100 values)
- [x] 9.7 Regenerate Python proto stubs from updated .proto files
- [x] 9.8 Write Python tests verifying fallback behavior when engine is unavailable
- [x] 9.9 Write Python tests verifying delegation when engine mock returns success

## 10. Integration and Verification

- [x] 10.1 End-to-end test: Python backend delegates authority resolution to running engine, results match expected format
- [x] 10.2 End-to-end test: Python backend falls back gracefully when engine is stopped
- [x] 10.3 Benchmark: compare Rust authority resolution vs Python on 1000-entity dataset, document speedup
- [x] 10.4 Benchmark: compare Rust disambiguation vs Python on 10k-value dataset
- [x] 10.5 Update engine health endpoint to report all registered pipelines by category
- [x] 10.6 Update backend `/engine/health` proxy to surface new pipeline info
