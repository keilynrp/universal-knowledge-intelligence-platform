# UKIP Rust Data Processing Engine — Design Spec

**Date:** 2026-05-08
**Status:** Reviewed (architecture review passed with fixes incorporated)
**Authors:** Jose Paul + Claude Opus 4.6

---

## 1. Overview

A Rust gRPC microservice (`ukip-engine`) that acts as a high-performance data processing engine for UKIP. It communicates with the FastAPI backend via gRPC and writes directly to PostgreSQL. Processing pipelines are defined as implementations of a `Pipeline` trait, starting with graph materialization and text analysis/NLP.

### Goals

- Replace the Python graph materializer (~8 min for 2,841 pubs) with a Rust engine (<10 seconds)
- Establish an extensible pipeline architecture for future data processing needs
- Validate correctness via shadow mode before cutover
- Zero disruption — UKIP works without the engine; it's an accelerator, not a requirement

### Non-Goals

- ML model inference (v2 scope)
- Real-time streaming ingestion
- Replacing the FastAPI backend

### Prerequisites (Phase 0)

Before the engine can be enabled, UKIP **must** be running on PostgreSQL. The engine uses PostgreSQL-specific features (`ON CONFLICT`, `IS NOT DISTINCT FROM`, `jsonb_set`, `ANY()` arrays, `COPY`) that are incompatible with SQLite. The SQLite backend remains functional for development without the engine (FastAPI fallback to Python materializer).

**Required migration before engine deployment:**

1. **Composite unique constraint on `raw_entities`:**
   ```sql
   CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_entities_canonical
   ON raw_entities (org_id, domain, entity_type, canonical_id)
   WHERE org_id IS NOT NULL;

   CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_entities_canonical_global
   ON raw_entities (domain, entity_type, canonical_id)
   WHERE org_id IS NULL;
   ```
   *Note: Partial indexes are needed because `NULL` org_id (legacy/global mode) is not equal to itself in a standard unique constraint.*

2. **Composite unique constraint on `entity_relationships`:**
   ```sql
   CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_relationships_pair
   ON entity_relationships (org_id, source_id, target_id, relation_type)
   WHERE org_id IS NOT NULL;

   CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_relationships_pair_global
   ON entity_relationships (source_id, target_id, relation_type)
   WHERE org_id IS NULL;
   ```

3. **Add `updated_at` column to `raw_entities`:**
   ```sql
   ALTER TABLE raw_entities ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
   ```

4. **Deduplicate existing data** that would violate the new constraints. A one-time script should merge duplicates keeping the most recent record.

---

## 2. Architecture

### Component Diagram

```
                    +----------------------------------------------+
                    |              Docker Compose                   |
                    |                                              |
+----------+       |  +--------------+  gRPC   +--------------+  |
| Frontend |<-REST-+--| ukip-backend |<------->|  ukip-engine |  |
| Next.js  |       |  |  (FastAPI)   |  :50051  |   (Rust)     |  |
+----------+       |  +------+-------+         +------+-------+  |
                    |         |                        |           |
                    |         |  SQLAlchemy            |  sqlx     |
                    |         v                        v           |
                    |  +--------------------------------------+   |
                    |  |          PostgreSQL 16                |   |
                    |  +--------------------------------------+   |
                    +----------------------------------------------+
```

### Key Decisions

| Decision | Choice | Justification |
|----------|--------|---------------|
| Async runtime | `tokio` | Standard for Rust async, excellent for I/O-bound gRPC + DB |
| gRPC framework | `tonic` | Native Rust, first-class tokio integration, codegen from .proto |
| PostgreSQL driver | `sqlx` | Async, compile-time query checking, COPY support, zero-cost |
| Serialization | `protobuf` (via tonic/prost) | Typed contract shared with Python (grpcio) |
| Logging | `tracing` | Structured logging, OpenTelemetry-compatible |
| Deployment | Separate container in docker-compose | Independent scaling, isolated resources, crash isolation |

### Sync/Async Hybrid Mode

```
Dataset < 500 records (configurable via ENGINE_SYNC_THRESHOLD):
  FastAPI --ProcessSync--> Engine --result--> FastAPI --response--> Client

Dataset >= 500 records:
  FastAPI --ProcessAsync--> Engine --ack + job_id--> FastAPI --202--> Client
                               |
                               +-- processes in background
                               +-- reports progress via streaming gRPC
                               +-- FastAPI polls status via GetJobStatus
```

---

## 3. gRPC Contract

### Service Definition

```protobuf
syntax = "proto3";
package ukip.engine.v1;

service Engine {
  rpc ProcessSync(ProcessRequest) returns (ProcessResponse);
  rpc ProcessAsync(ProcessRequest) returns (JobAccepted);
  rpc GetJobStatus(JobStatusRequest) returns (JobStatusResponse);
  rpc StreamProgress(JobStatusRequest) returns (stream ProgressEvent);
  rpc Health(HealthRequest) returns (HealthResponse);
}
```

### Input Messages

```protobuf
message ProcessRequest {
  string pipeline = 1;           // "graph_materialization", "text_analysis"
  string job_id = 2;             // UUID generated by FastAPI
  int64 import_batch_id = 3;
  optional int64 org_id = 4;
  string domain = 5;             // "science", "healthcare", etc.
  repeated Publication publications = 6;
  map<string, string> options = 7;  // per-pipeline config
}

message Publication {
  int64 entity_id = 1;           // raw_entities.id already persisted
  string title = 2;
  optional string doi = 3;
  optional int32 year = 4;
  optional string abstract_text = 5;
  optional string source_title = 6;
  optional string publisher = 7;
  optional string publication_type = 8;
  optional int32 citation_count = 9;
  optional int32 reference_count = 10;
  repeated Author authors = 11;
  repeated Affiliation affiliations = 12;
  repeated Identifier identifiers = 13;
  repeated string concepts = 14;
  optional string enrichment_source = 15;
  optional string attributes_json = 16;   // Raw attributes for fallback parsing
  optional string enrichment_doi = 17;    // Already-persisted DOI to merge into identifiers
}

message Author {
  string name = 1;
  optional int32 order = 2;
  optional string orcid = 3;
  optional string external_id = 4;
  repeated string affiliations = 5;
}

message Affiliation {
  string name = 1;
  optional string country = 2;
  optional string external_id = 3;
}

message Identifier {
  string scheme = 1;
  string value = 2;
}
```

### Output Messages

```protobuf
message ProcessResponse {
  string job_id = 1;
  string pipeline = 2;
  Status status = 3;
  ProcessResult result = 4;
  optional string error = 5;
  double duration_ms = 6;
}

message ProcessResult {
  int32 nodes_created = 1;
  int32 nodes_deduplicated = 2;
  int32 relationships_created = 3;
  int32 relationships_deduplicated = 4;
  int32 keywords_extracted = 5;
  int32 entities_classified = 6;
  map<string, int32> counters = 10;  // extensible without breaking proto
}

message JobAccepted {
  string job_id = 1;
  string pipeline = 2;
  int64 estimated_duration_ms = 3;  // int64 to avoid overflow for large datasets
}

message JobStatusRequest {
  string job_id = 1;
}

message JobStatusResponse {
  string job_id = 1;
  Status status = 2;
  float progress = 3;           // 0.0 - 1.0
  optional ProcessResult result = 4;
  optional string error = 5;
}

message ProgressEvent {
  string job_id = 1;
  float progress = 2;
  string phase = 3;             // "parsing", "dedup", "writing_nodes", "writing_relationships"
  string message = 4;
  map<string, int32> counters = 5;
}

message HealthRequest {}
message HealthResponse {
  bool healthy = 1;
  string version = 2;
  repeated string pipelines = 3;
  int32 active_jobs = 4;
}

enum Status {
  STATUS_UNKNOWN = 0;
  STATUS_QUEUED = 1;
  STATUS_RUNNING = 2;
  STATUS_COMPLETED = 3;
  STATUS_FAILED = 4;
}
```

### Contract Design Notes

| Decision | Reason |
|----------|--------|
| `map<string, int32> counters` in ProcessResult | Future pipelines report metrics without modifying the proto |
| `Publication.entity_id` required | Engine writes relationships referencing entities already persisted by FastAPI |
| Generic `options` map | Each pipeline interprets its own options without contaminating the proto |
| `v1` in package name | Allows breaking evolution in `v2` without breaking existing clients |
| `phase` in ProgressEvent | Frontend can show granular progress ("Writing nodes... 45%") |
| `attributes_json` on Publication | Engine can parse raw_record sub-keys (DE, ID, SO) for concept/journal fallback, same as Python |
| `enrichment_doi` on Publication | Python materializer merges this into identifiers (line 364-365); engine needs it too |

---

## 4. Pipeline Architecture

### Project Structure

```
engine/
+-- proto/
|   +-- ukip/engine/v1/engine.proto
+-- src/
|   +-- main.rs                    # Tokio runtime + gRPC server bootstrap
|   +-- config.rs                  # Env vars, defaults, validation
|   +-- server.rs                  # gRPC Engine service implementation
|   +-- router.rs                  # Dispatches ProcessRequest to correct pipeline
|   +-- jobs.rs                    # Job registry (in-memory for async jobs)
|   +-- db/
|   |   +-- mod.rs
|   |   +-- pool.rs                # sqlx::PgPool wrapper + health check
|   |   +-- bulk_writer.rs         # Batch INSERT ON CONFLICT, COPY
|   |   +-- schema.rs              # Structs mapping to target tables
|   +-- pipelines/
|   |   +-- mod.rs                 # Pipeline trait + PipelineRegistry
|   |   +-- graph/
|   |   |   +-- mod.rs             # GraphMaterializationPipeline
|   |   |   +-- canonical.rs       # Canonical ID generation, slug, dedup
|   |   |   +-- nodes.rs           # Node extraction: author, affiliation, journal, concept, identifier
|   |   |   +-- relationships.rs   # Relationship computation + coauthor pairs
|   |   |   +-- dedup.rs           # Cross-batch deduplication (fuzzy matching)
|   |   +-- text_analysis/
|   |       +-- mod.rs             # TextAnalysisPipeline
|   |       +-- keywords.rs        # TF-IDF keyword extraction
|   |       +-- classifier.rs      # Entity type classification (rule-based)
|   |       +-- tokenizer.rs       # Unicode-aware tokenization
|   |       +-- language.rs        # Trigram-based language detection
|   +-- progress.rs                # ProgressTracker (broadcast channel -> gRPC stream)
+-- tests/
|   +-- common/mod.rs
|   +-- test_graph_pipeline.rs
|   +-- test_text_pipeline.rs
|   +-- test_bulk_writer.rs
|   +-- test_dedup.rs
+-- benches/
|   +-- graph_materialization.rs
|   +-- text_analysis.rs
+-- Cargo.toml
+-- Dockerfile
+-- build.rs                       # Proto compilation (tonic-build)
```

### Pipeline Trait

```rust
#[async_trait]
pub trait Pipeline: Send + Sync + 'static {
    fn name(&self) -> &'static str;

    fn validate(&self, input: &PipelineInput) -> Result<(), ValidationError> {
        if input.publications.is_empty() {
            return Err(ValidationError::EmptyInput);
        }
        Ok(())
    }

    async fn process(
        &self,
        input: PipelineInput,
        ctx: &PipelineContext,
    ) -> Result<PipelineOutput, PipelineError>;
}
```

### Pipeline Registry

```rust
pub struct PipelineRegistry {
    pipelines: HashMap<String, Arc<dyn Pipeline>>,
}

impl PipelineRegistry {
    pub fn new() -> Self {
        let mut registry = Self { pipelines: HashMap::new() };
        registry.register(Arc::new(GraphMaterializationPipeline::new()));
        registry.register(Arc::new(TextAnalysisPipeline::new()));
        registry
    }

    pub fn get(&self, name: &str) -> Option<Arc<dyn Pipeline>> {
        self.pipelines.get(name).cloned()
    }

    pub fn list(&self) -> Vec<&str> {
        self.pipelines.keys().map(|k| k.as_str()).collect()
    }
}
```

### Job Manager

Uses `DashMap` (lock-free concurrent HashMap) for in-memory job state. Jobs are spawned as tokio tasks and update their state atomically.

---

## 5. Bulk Writer — PostgreSQL Write Strategy

### Problem

The Python materializer makes ~76,000 individual SQL queries for 2,841 publications (1 SELECT + 1 INSERT per node/relationship).

### Solution: Two-Phase Write

**Phase 1 — In-memory accumulation** (zero DB queries):
- Pipeline processes publications into `HashSet<PendingNode>` (dedup in RAM)
- Relationships accumulated as `Vec<PendingRelationship>` with canonical ID references

**Phase 2 — Batch write:**

```
flush_nodes():
  INSERT INTO raw_entities (...) VALUES ($1,$2,...), ($3,$4,...), ...
  ON CONFLICT (org_id, domain, entity_type, canonical_id)
  DO UPDATE SET updated_at = NOW()
  RETURNING id, canonical_id
  -> Chunks of 1000 rows per statement
  -> Maps canonical_id -> DB id

flush_relationships():
  INSERT INTO entity_relationships (...)
  VALUES (...), (...), ...
  ON CONFLICT (org_id, source_id, target_id, relation_type)
  DO NOTHING
  -> Chunks of 2000 rows per statement
```

### Cross-Batch Deduplication

Before `flush_nodes()`, a single query resolves existing nodes from previous batches:

```sql
SELECT id, canonical_id FROM raw_entities
WHERE org_id IS NOT DISTINCT FROM $1
AND domain = $2
AND canonical_id = ANY($3)
```

### Expected Performance

| Metric | Python (current) | Rust engine |
|--------|-----------------|-------------|
| SQL queries | ~76,000 individual | ~80 batches |
| DB round-trips | 76,000 | 80 |
| Dedup strategy | In-DB (SELECT each) | In-memory HashSet + 1 bulk SELECT |
| Cross-batch dedup | None (duplicates everything) | 1 SELECT with ANY($ids) |
| Time (2,841 pubs) | ~8 minutes | <10 seconds |
| Memory | Low (row by row) | ~50-100 MB (accumulates in RAM) |

---

## 6. Pipeline 1: Graph Materialization

### Behavior Change: Cross-Batch Deduplication

The Python materializer scopes dedup to `import_batch_id` — the same canonical author appearing in two different batches creates two separate rows. The Rust engine intentionally changes this behavior to deduplicate across batches using `ON CONFLICT (org_id, domain, entity_type, canonical_id)`.

**This is a deliberate improvement, not a bug.** It means:
- Uploading the same file twice produces 0 new derived nodes (correct)
- Authors appearing across multiple imports are unified into a single node (correct)
- The parity test (G1, G2) must account for this: it validates against **expected Rust behavior** (a separate fixture), not Python output

**Shadow mode handling:** During shadow mode, the comparator expects and logs the difference in node counts as `expected_dedup_delta`, not as a discrepancy. The comparison focuses on:
- All canonical_ids from Python output exist in Rust output (subset check)
- All relationship types are present with correct source/target canonical_ids
- No data corruption (no orphaned relationships)

### Entity Types Created

| Type | Canonical ID Pattern | Source |
|------|---------------------|--------|
| author | `orcid:<orcid>` or `author:<external_id>` or `author:<name>` | `canonical_authors` |
| affiliation | `affiliation:<external_id>` or `affiliation:<name>` | `canonical_affiliations` |
| journal | `journal:<source_title>` | `primary_location.source` |
| concept | `concept:<concept_name>` | `concepts`, `topics`, `keywords` |
| identifier | `<scheme>:<value>` | `canonical_identifiers` |

### Relationship Types Created

| Type | Source -> Target | Weight |
|------|-----------------|--------|
| authored-by | publication -> author | 1.0 |
| belongs-to | author -> affiliation | 1.0 |
| published-in | publication -> journal | 1.0 |
| has-concept | publication -> concept | 0.7 |
| identified-by | publication -> identifier | 0.5 |
| coauthor-with | author -> author (ordered by canonical_id, ascending) | 0.8 |

### Implementation Notes

- **Derived source value:** The engine writes `source = "graph_materializer"` (same as Python) for shadow mode parity. After cutover, this may be changed to `"ukip_engine"` for provenance tracking.
- **Coauthor pair ordering:** Python orders by `sorted((left.id, right.id))` using DB ids. Rust orders by `canonical_id` string sort since DB ids are not known during in-memory accumulation. The parity test validates relationship existence by `(source_canonical, target_canonical, type)` tuples, which is order-independent.

---

## 7. Pipeline 2: Text Analysis / NLP

### Scope (v1)

1. **TF-IDF keyword extraction** — over titles + abstracts within the batch
2. **Entity type classification** — rule-based refinement of `publication_type`
3. **Language detection** — trigram frequency matching

### Components

**Tokenizer:** Unicode-aware, stopword removal (embedded via `include_str!`), lowercase normalization.

**TF-IDF Extractor:** Calculates TF-IDF over the entire batch corpus. Returns top-N keywords per document. Parameters: `max_keywords=10`, `min_df=0.01`, `max_df=0.90`.

**Language Detector:** Trigram frequency matching against pre-computed profiles. Supports: en, es, fr, de, pt, it, zh, ja, ko. ~95% accuracy for texts >50 chars.

**Entity Type Classifier:** Rule-based with ordered priority:
- DOI prefix `10.48550` -> preprint (arXiv), confidence 0.95
- No source_title + no publisher -> preprint, confidence 0.70
- source_title contains "conference"/"proceedings" -> conference_paper, confidence 0.85

### DB Writes

Batch UPDATE using `unnest` arrays (chunks of 500):
```sql
UPDATE raw_entities AS r SET
  enrichment_concepts = data.concepts,
  attributes_json = jsonb_set(
    COALESCE(r.attributes_json::jsonb, '{}'),
    '{detected_language}',
    to_jsonb(data.lang)
  )
FROM (
  SELECT unnest($1::int[]) AS id,
         unnest($2::text[]) AS concepts,
         unnest($3::text[]) AS lang
) AS data
WHERE r.id = data.id
```

### Design Notes

| Decision | Reason |
|----------|--------|
| Pure TF-IDF, no ML models | Zero external dependencies, deterministic, fast. 10K docs in <1s |
| Trigram language detection | Proven technique, ~100 lines implementation |
| Rule-based classifier | Transparent, debuggable, no training data needed |
| No embeddings in v1 | Would require ONNX runtime — scope for v2 |

---

## 8. Shadow Mode and Transition

### Phases

```
Phase 1: DEPLOY (no engine)
  ENGINE_GRPC_URL=""
  -> FastAPI uses Python materializer
  -> Zero risk, current behavior

Phase 2: SHADOW MODE
  ENGINE_GRPC_URL=ukip-engine:50051
  ENGINE_SHADOW_MODE=true
  -> FastAPI runs Python (real) + Rust (shadow tables), compares
  -> Validates with real data

Phase 3: CUTOVER
  ENGINE_SHADOW_MODE=false
  ENGINE_FALLBACK_PYTHON=true
  -> FastAPI uses Rust, falls back to Python if engine down

Phase 4: FULL RUST
  ENGINE_FALLBACK_PYTHON=false
  -> FastAPI depends on engine, 503 if unavailable
```

### Shadow Tables

```sql
CREATE TABLE IF NOT EXISTS _shadow_raw_entities (LIKE raw_entities INCLUDING ALL);
CREATE TABLE IF NOT EXISTS _shadow_entity_relationships (LIKE entity_relationships INCLUDING ALL);
```

### Graduation Criteria

- 0 discrepancies during 20 consecutive imports with real data
- At least 1 import of >1000 publications with zero discrepancies
- Shadow tables dropped on disable

### FastAPI Integration

**New module:** `backend/services/engine_client.py` — async gRPC client wrapping the Engine service.

**Changes to `ingest.py`:**
```python
engine = request.app.state.engine_client
if engine and await engine.health():
    graph_result = await engine.process(...)
else:
    graph_result = materialize_scientific_import_graph(...)  # fallback
```

**New endpoints:**
- `GET /engine/jobs/{job_id}` — poll async job status
- `GET /engine/health` — engine health + registered pipelines

---

## 9. Infrastructure

### Docker Compose Addition

```yaml
ukip-engine:
  build:
    context: ./engine
    dockerfile: Dockerfile
  restart: unless-stopped
  depends_on:
    postgres:
      condition: service_healthy
  environment:
    ENGINE_DATABASE_URL: postgresql://ukip:ukip_secret@postgres:5432/ukip
    ENGINE_GRPC_PORT: "50051"
    ENGINE_LOG_LEVEL: debug
    RUST_BACKTRACE: "1"
  healthcheck:
    test: ["CMD", "/app/engine", "--health-check"]
    interval: 10s
    timeout: 5s
    retries: 3
```

### Dockerfile (multi-stage)

- **Build:** `rust:1.82-slim` + protobuf-compiler, cargo dependency caching
- **Runtime:** `debian:bookworm-slim` (~80MB), binary only

### gRPC Security

The gRPC channel is internal to the Docker Compose network. Port 50051 must **never** be published to the host network in production.

Authentication uses a shared secret via gRPC metadata:
- Engine validates `x-engine-token` header on every request
- Token set via `ENGINE_AUTH_TOKEN` env var (shared between FastAPI and engine)
- Requests without valid token receive `UNAUTHENTICATED` status

### Graceful Shutdown

On `SIGTERM` (Docker stop):
1. Stop accepting new jobs (`ProcessSync` and `ProcessAsync` return `UNAVAILABLE`)
2. Wait for in-flight async jobs to complete (timeout: `ENGINE_SHUTDOWN_TIMEOUT_SECS`, default 60)
3. Mark incomplete jobs as `STATUS_FAILED` with error "engine shutdown"
4. Close DB connection pool
5. Exit

### Concurrency Limits

- `ENGINE_MAX_CONCURRENT_JOBS` (default 4) — max async jobs running simultaneously
- Jobs beyond this limit receive `RESOURCE_EXHAUSTED` gRPC status with a retry-after hint
- Sync requests (`ProcessSync`) are not limited but share the DB pool

### Job State Persistence (v1 limitation)

In v1, job state is in-memory (`DashMap`). If the engine crashes during an async job:
- Job status becomes unknown to FastAPI
- FastAPI client handles this by treating unknown job_ids as failed
- `ENGINE_FALLBACK_PYTHON=true` ensures the data can be reprocessed via Python
- v2 may persist job state to an `engine_jobs` PostgreSQL table

### Environment Variables

```bash
# Engine (Rust)
ENGINE_DATABASE_URL=postgresql://...
ENGINE_GRPC_PORT=50051
ENGINE_LOG_LEVEL=info
ENGINE_NODE_CHUNK_SIZE=1000
ENGINE_REL_CHUNK_SIZE=2000
ENGINE_AUTH_TOKEN=<shared-secret>
ENGINE_MAX_CONCURRENT_JOBS=4
ENGINE_SHUTDOWN_TIMEOUT_SECS=60

# FastAPI
ENGINE_GRPC_URL=ukip-engine:50051      # empty = disabled
ENGINE_SYNC_THRESHOLD=500
ENGINE_SHADOW_MODE=false
ENGINE_FALLBACK_PYTHON=true
ENGINE_AUTH_TOKEN=<same-shared-secret>
```

---

## 10. Testing and Acceptance Criteria

### Test Strategy

| Layer | Tool | DB Required |
|-------|------|-------------|
| Unit tests | `cargo test` | No |
| Integration tests | `cargo test --features integration` | Yes (test DB) |
| gRPC tests | `cargo test --features grpc` | Yes (server + DB) |
| Benchmarks | `criterion` | Yes |
| Shadow mode tests | `pytest` | Yes |
| Parity test | `cargo test` + Python fixture | Yes |

### Acceptance Criteria — Graph Materialization

| # | Criterion | Verification |
|---|----------|-------------|
| G1 | Produces same nodes as Python for WoS 2,841 pub dataset | Parity test |
| G2 | Produces same relationships as Python | Parity test |
| G3 | Cross-batch dedup: uploading same file twice does not duplicate nodes | Integration test |
| G4 | Performance: 2,841 pubs in <10 seconds | Benchmark |
| G5 | Performance: 10,000 pubs in <30 seconds | Benchmark |
| G6 | Sync mode works for <500 pubs | gRPC test |
| G7 | Async mode works for >=500 pubs with progress | gRPC test |
| G8 | Fallback to Python when engine unavailable | Integration test |

### Acceptance Criteria — Text Analysis

| # | Criterion | Verification |
|---|----------|-------------|
| T1 | Extracts >=3 relevant keywords per publication with abstract | Unit test + manual review |
| T2 | Does not extract stopwords or terms with TF-IDF < threshold | Unit test |
| T3 | Detects language correctly for EN, ES, FR, DE, PT (>90% accuracy) | Unit test with known corpus |
| T4 | Classifies arXiv preprints by DOI prefix | Unit test |
| T5 | Writes results to DB in batch | Integration test |
| T6 | Performance: 10,000 abstracts in <5 seconds | Benchmark |

### Acceptance Criteria — Shadow Mode

| # | Criterion | Verification |
|---|----------|-------------|
| S1 | Shadow mode runs both without affecting real data | Integration test |
| S2 | Comparator detects discrepancies and logs them | Integration test |
| S3 | Shadow tables cleaned on disable | Integration test |
| S4 | 0 discrepancies in 20 consecutive imports -> ready for cutover | Operational |

### Acceptance Criteria — Infrastructure

| # | Criterion | Verification |
|---|----------|-------------|
| I1 | `docker compose up` starts engine + postgres + backend | Manual |
| I2 | Health check reports registered pipelines | gRPC test |
| I3 | Engine starts in <2 seconds | Observation |
| I4 | Engine handles empty, malformed, and extreme unicode input | Fuzz test |
| I5 | Structured logs with tracing (JSON in production) | Observation |

### Coverage Targets

| Component | Target |
|-----------|--------|
| Unit tests (Rust) | >=85% |
| Integration tests (Rust) | Happy path + error paths per pipeline |
| gRPC tests | Each RPC method |
| Shadow mode tests (Python) | >=80% |
| Benchmarks | 3 dataset sizes per pipeline |

---

## 11. Rust Crate Dependencies

```toml
[dependencies]
tokio = { version = "1", features = ["full"] }
tonic = "0.12"
prost = "0.13"
sqlx = { version = "0.8", features = ["runtime-tokio", "postgres", "macros"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
dashmap = "6"
async-trait = "0.1"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["json", "env-filter"] }
uuid = { version = "1", features = ["v4"] }
unicode-segmentation = "1"
unicode-normalization = "0.1"

[build-dependencies]
tonic-build = "0.12"

[dev-dependencies]
criterion = { version = "0.5", features = ["async_tokio"] }
tokio-test = "0.4"
```
