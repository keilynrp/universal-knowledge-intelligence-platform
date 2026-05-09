# Rust gRPC Data Processing Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Rust gRPC microservice (`ukip-engine`) that replaces the Python graph materializer with a high-performance pipeline architecture, starting with graph materialization and text analysis.

**Architecture:** A Tonic gRPC server with sqlx async PostgreSQL access, using a Pipeline trait for extensible data processing. Communicates with FastAPI via protobuf. Includes shadow mode for safe validation before cutover.

**Tech Stack:** Rust, Tonic (gRPC), sqlx (PostgreSQL), tokio (async), prost (protobuf), tracing (logging), DashMap (concurrent state), criterion (benchmarks)

**Spec:** `docs/superpowers/specs/2026-05-08-rust-engine-design.md`

---

## File Structure

### New Files (Rust Engine)

| File | Responsibility |
|------|---------------|
| `engine/Cargo.toml` | Crate config, dependencies, features |
| `engine/build.rs` | Tonic protobuf compilation |
| `engine/Dockerfile` | Multi-stage build (rust:1.82-slim → debian:bookworm-slim) |
| `engine/proto/ukip/engine/v1/engine.proto` | gRPC service + message definitions |
| `engine/src/lib.rs` | Library crate: re-exports all modules + proto (integration tests import from here) |
| `engine/src/main.rs` | Tokio runtime bootstrap, CLI health-check flag, gRPC server start |
| `engine/src/config.rs` | Env var parsing, defaults, validation |
| `engine/src/server.rs` | `Engine` gRPC service trait impl (5 RPCs) |
| `engine/src/router.rs` | Pipeline dispatch from ProcessRequest.pipeline name |
| `engine/src/jobs.rs` | In-memory job registry (DashMap), spawn/track/cancel |
| `engine/src/progress.rs` | ProgressTracker with broadcast channel → gRPC stream |
| `engine/src/db/mod.rs` | DB module re-exports |
| `engine/src/db/pool.rs` | sqlx::PgPool wrapper + health check |
| `engine/src/db/bulk_writer.rs` | Batch INSERT ON CONFLICT, chunked writes |
| `engine/src/db/schema.rs` | Rust structs mapping to raw_entities / entity_relationships |
| `engine/src/pipelines/mod.rs` | Pipeline trait + PipelineRegistry |
| `engine/src/pipelines/graph/mod.rs` | GraphMaterializationPipeline |
| `engine/src/pipelines/graph/canonical.rs` | Canonical ID generation, slug, dedup |
| `engine/src/pipelines/graph/nodes.rs` | Node extraction: author, affiliation, journal, concept, identifier |
| `engine/src/pipelines/graph/relationships.rs` | Relationship computation + coauthor pairs |
| `engine/src/pipelines/graph/dedup.rs` | Cross-batch deduplication (bulk SELECT) |
| `engine/src/pipelines/text_analysis/mod.rs` | TextAnalysisPipeline |
| `engine/src/pipelines/text_analysis/keywords.rs` | TF-IDF keyword extraction |
| `engine/src/pipelines/text_analysis/classifier.rs` | Entity type classification (rule-based) |
| `engine/src/pipelines/text_analysis/tokenizer.rs` | Unicode-aware tokenization + stopwords |
| `engine/src/pipelines/text_analysis/language.rs` | Trigram-based language detection |
| `engine/tests/common/mod.rs` | Test helpers, DB fixture setup |
| `engine/tests/test_graph_pipeline.rs` | Graph materialization integration tests |
| `engine/tests/test_text_pipeline.rs` | Text analysis integration tests |
| `engine/tests/test_bulk_writer.rs` | Bulk writer integration tests |
| `engine/tests/test_dedup.rs` | Dedup unit + integration tests |
| `engine/benches/graph_materialization.rs` | Criterion benchmarks |
| `engine/benches/text_analysis.rs` | Criterion benchmarks |

### New Files (Python Integration)

| File | Responsibility |
|------|---------------|
| `backend/services/engine_client.py` | Async gRPC client wrapping Engine service |
| `backend/routers/engine.py` | `GET /engine/health`, `GET /engine/jobs/{job_id}` |
| `tests/test_engine_client.py` | Engine client unit tests (mocked gRPC) |

### Modified Files

| File | Change |
|------|--------|
| `alembic/versions/xxxx_engine_prereqs.py` | Migration: unique indexes + updated_at column |
| `backend/models.py` | Add `updated_at` column to UniversalEntity |
| `backend/routers/ingest.py` | Engine integration: try engine → fallback to Python |
| `backend/main.py` | Include engine router, init engine_client in lifespan |
| `docker-compose.yml` | Add ukip-engine service |
| `requirements.txt` | Add `grpcio`, `grpcio-tools`, `protobuf` |

---

## Phase 0: PostgreSQL Prerequisites

### Task 1: Database Migration — Unique Constraints + updated_at

**Files:**
- Create: `alembic/versions/a1b2c3d4e5f6_engine_prerequisites.py`
- Modify: `backend/models.py:7-42`
- Test: `tests/test_engine_prereqs.py`

- [ ] **Step 1: Write the migration test**

```python
# tests/test_engine_prereqs.py
"""Tests for engine prerequisite DB constraints."""
import pytest
from sqlalchemy import inspect, text


class TestEnginePrereqMigration:
    def test_updated_at_column_exists(self, db_session):
        result = db_session.execute(text(
            "SELECT sql FROM sqlite_master WHERE name='raw_entities'"
        )).scalar()
        # For SQLite dev, column exists. For Postgres, use inspect.
        # This test validates the model has the column.
        from backend.models import UniversalEntity
        assert hasattr(UniversalEntity, 'updated_at')

    def test_unique_constraint_indexes_defined(self, db_session):
        """Validate that the model is consistent. Actual index creation is Postgres-only."""
        from backend.models import UniversalEntity, EntityRelationship
        # Verify columns used in constraint exist
        mapper = inspect(UniversalEntity)
        col_names = [c.key for c in mapper.column_attrs]
        assert 'org_id' in col_names
        assert 'domain' in col_names
        assert 'entity_type' in col_names
        assert 'canonical_id' in col_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:/universal-knowledge-intelligence-platform && .venv/Scripts/python -m pytest tests/test_engine_prereqs.py -v`
Expected: FAIL — `updated_at` attribute missing on UniversalEntity

- [ ] **Step 3: Add updated_at to UniversalEntity model**

In `backend/models.py`, add after line 37 (quality_score):
```python
    # Engine sync
    updated_at = Column(DateTime, nullable=True)
```

- [ ] **Step 4: Write the Alembic migration**

```python
# alembic/versions/a1b2c3d4e5f6_engine_prerequisites.py
"""Engine prerequisites: unique constraints + updated_at

Revision ID: a1b2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = None  # Set to latest revision ID
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add updated_at column
    op.add_column('raw_entities', sa.Column('updated_at', sa.DateTime(), nullable=True))

    # 2. Partial unique indexes (PostgreSQL only — SQLite ignores WHERE clause)
    # raw_entities: org_id present
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_entities_canonical
        ON raw_entities (org_id, domain, entity_type, canonical_id)
        WHERE org_id IS NOT NULL
    """)
    # raw_entities: org_id NULL (global/legacy)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_entities_canonical_global
        ON raw_entities (domain, entity_type, canonical_id)
        WHERE org_id IS NULL
    """)
    # entity_relationships: org_id present
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_relationships_pair
        ON entity_relationships (org_id, source_id, target_id, relation_type)
        WHERE org_id IS NOT NULL
    """)
    # entity_relationships: org_id NULL
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_relationships_pair_global
        ON entity_relationships (source_id, target_id, relation_type)
        WHERE org_id IS NULL
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_entity_relationships_pair_global")
    op.execute("DROP INDEX IF EXISTS uq_entity_relationships_pair")
    op.execute("DROP INDEX IF EXISTS uq_raw_entities_canonical_global")
    op.execute("DROP INDEX IF EXISTS uq_raw_entities_canonical")
    op.drop_column('raw_entities', 'updated_at')
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_engine_prereqs.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/models.py alembic/versions/a1b2c3d4e5f6_engine_prerequisites.py tests/test_engine_prereqs.py
git commit -m "feat: add engine prerequisite migration (unique constraints + updated_at)"
```

---

## Phase 1: Rust Project Scaffolding

### Task 2: Initialize Cargo Project + Proto Definition

**Files:**
- Create: `engine/Cargo.toml`
- Create: `engine/build.rs`
- Create: `engine/proto/ukip/engine/v1/engine.proto`
- Create: `engine/src/main.rs` (minimal stub)

- [ ] **Step 1: Create the engine directory structure**

```bash
mkdir -p engine/proto/ukip/engine/v1
mkdir -p engine/src/db
mkdir -p engine/src/pipelines/graph
mkdir -p engine/src/pipelines/text_analysis
mkdir -p engine/tests/common
mkdir -p engine/benches
```

- [ ] **Step 2: Write Cargo.toml**

```toml
[package]
name = "ukip-engine"
version = "0.1.0"
edition = "2021"

[[bin]]
name = "engine"
path = "src/main.rs"

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
regex = "1"
thiserror = "2"

[build-dependencies]
tonic-build = "0.12"

[dev-dependencies]
criterion = { version = "0.5", features = ["async_tokio"] }
tokio-test = "0.4"

[features]
integration = []
grpc = []

[[bench]]
name = "graph_materialization"
harness = false

[[bench]]
name = "text_analysis"
harness = false
```

- [ ] **Step 3: Write the proto file**

Copy the full protobuf definition from spec Section 3 into `engine/proto/ukip/engine/v1/engine.proto`. Include all messages: ProcessRequest, Publication, Author, Affiliation, Identifier, ProcessResponse, ProcessResult, JobAccepted, JobStatusRequest, JobStatusResponse, ProgressEvent, HealthRequest, HealthResponse, Status enum.

- [ ] **Step 4: Write build.rs**

```rust
fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::configure()
        .build_server(true)
        .build_client(true)
        .compile_protos(
            &["proto/ukip/engine/v1/engine.proto"],
            &["proto"],
        )?;
    Ok(())
}
```

- [ ] **Step 5: Write lib.rs (library crate for integration tests)**

```rust
// engine/src/lib.rs
pub mod config;
pub mod db;
pub mod jobs;
pub mod pipelines;
pub mod progress;
pub mod router;
pub mod server;

pub mod proto {
    tonic::include_proto!("ukip.engine.v1");
}
```

- [ ] **Step 6: Write minimal main.rs stub**

```rust
// engine/src/main.rs
use std::process;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|a| a == "--health-check") {
        // TODO: implement real health check via gRPC reflection
        println!("healthy");
        process::exit(0);
    }
    println!("ukip-engine v0.1.0 — not yet implemented");
}
```

- [ ] **Step 7: Verify it compiles**

```bash
cd engine && cargo build 2>&1
```
Expected: Successful build, proto files compiled by tonic-build.

- [ ] **Step 8: Commit**

```bash
git add engine/
git commit -m "feat: scaffold Rust engine project with proto definition"
```

---

### Task 3: Config Module

**Files:**
- Create: `engine/src/config.rs`
- Test: inline `#[cfg(test)]`

- [ ] **Step 1: Write config test**

```rust
// At bottom of config.rs
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        // Clear env to test defaults
        let config = Config {
            database_url: "postgresql://test:test@localhost/test".to_string(),
            grpc_port: 50051,
            log_level: "info".to_string(),
            node_chunk_size: 1000,
            rel_chunk_size: 2000,
            auth_token: None,
            max_concurrent_jobs: 4,
            shutdown_timeout_secs: 60,
        };
        assert_eq!(config.grpc_port, 50051);
        assert_eq!(config.node_chunk_size, 1000);
    }

    #[test]
    fn test_config_from_env() {
        std::env::set_var("ENGINE_DATABASE_URL", "postgresql://x:x@localhost/x");
        std::env::set_var("ENGINE_GRPC_PORT", "9999");
        let config = Config::from_env().unwrap();
        assert_eq!(config.grpc_port, 9999);
        std::env::remove_var("ENGINE_DATABASE_URL");
        std::env::remove_var("ENGINE_GRPC_PORT");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd engine && cargo test config::tests -v`
Expected: FAIL — Config struct not defined

- [ ] **Step 3: Implement Config**

```rust
// engine/src/config.rs
use std::env;

#[derive(Debug, Clone)]
pub struct Config {
    pub database_url: String,
    pub grpc_port: u16,
    pub log_level: String,
    pub node_chunk_size: usize,
    pub rel_chunk_size: usize,
    pub auth_token: Option<String>,
    pub max_concurrent_jobs: usize,
    pub shutdown_timeout_secs: u64,
}

impl Config {
    pub fn from_env() -> Result<Self, String> {
        let database_url = env::var("ENGINE_DATABASE_URL")
            .map_err(|_| "ENGINE_DATABASE_URL is required")?;

        Ok(Self {
            database_url,
            grpc_port: parse_env("ENGINE_GRPC_PORT", 50051),
            log_level: env::var("ENGINE_LOG_LEVEL").unwrap_or_else(|_| "info".to_string()),
            node_chunk_size: parse_env("ENGINE_NODE_CHUNK_SIZE", 1000),
            rel_chunk_size: parse_env("ENGINE_REL_CHUNK_SIZE", 2000),
            auth_token: env::var("ENGINE_AUTH_TOKEN").ok(),
            max_concurrent_jobs: parse_env("ENGINE_MAX_CONCURRENT_JOBS", 4),
            shutdown_timeout_secs: parse_env("ENGINE_SHUTDOWN_TIMEOUT_SECS", 60),
        })
    }
}

fn parse_env<T: std::str::FromStr>(key: &str, default: T) -> T {
    env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd engine && cargo test config::tests`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/src/config.rs
git commit -m "feat(engine): add config module with env var parsing"
```

---

### Task 4: DB Pool Module

**Files:**
- Create: `engine/src/db/mod.rs`
- Create: `engine/src/db/pool.rs`
- Create: `engine/src/db/schema.rs`

- [ ] **Step 1: Write DB schema structs**

```rust
// engine/src/db/schema.rs
use serde::{Deserialize, Serialize};

/// Mirrors raw_entities table for INSERT
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PendingNode {
    pub org_id: Option<i64>,
    pub import_batch_id: Option<i64>,
    pub domain: String,
    pub entity_type: String,
    pub primary_label: String,
    pub secondary_label: Option<String>,
    pub canonical_id: String,
    pub attributes_json: String,
    pub source: String,
    pub enrichment_source: Option<String>,
    pub enrichment_concepts: Option<String>,
}

/// Mirrors entity_relationships table for INSERT
#[derive(Debug, Clone)]
pub struct PendingRelationship {
    pub org_id: Option<i64>,
    pub source_canonical_id: String,
    pub target_canonical_id: String,
    pub relation_type: String,
    pub weight: f64,
}

/// Returned from flush_nodes RETURNING clause
#[derive(Debug, Clone, sqlx::FromRow)]
pub struct InsertedNode {
    pub id: i64,
    pub canonical_id: String,
}
```

- [ ] **Step 2: Write pool module**

```rust
// engine/src/db/pool.rs
use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;

pub async fn create_pool(database_url: &str) -> Result<PgPool, sqlx::Error> {
    PgPoolOptions::new()
        .max_connections(20)
        .connect(database_url)
        .await
}

pub async fn health_check(pool: &PgPool) -> bool {
    sqlx::query_scalar::<_, i32>("SELECT 1")
        .fetch_one(pool)
        .await
        .is_ok()
}
```

- [ ] **Step 3: Write db mod.rs**

```rust
// engine/src/db/mod.rs
pub mod pool;
pub mod schema;
pub mod bulk_writer;
```

- [ ] **Step 4: Verify it compiles**

Run: `cd engine && cargo check`
Expected: Compiles (bulk_writer doesn't exist yet — create empty file)

- [ ] **Step 5: Commit**

```bash
git add engine/src/db/
git commit -m "feat(engine): add DB pool and schema modules"
```

---

### Task 5: Pipeline Trait + Registry

**Files:**
- Create: `engine/src/pipelines/mod.rs`
- Test: inline `#[cfg(test)]`

- [ ] **Step 1: Write pipeline trait test**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    struct DummyPipeline;

    #[async_trait::async_trait]
    impl Pipeline for DummyPipeline {
        fn name(&self) -> &'static str { "dummy" }

        async fn process(
            &self,
            _input: PipelineInput,
            _ctx: &PipelineContext,
        ) -> Result<PipelineOutput, PipelineError> {
            Ok(PipelineOutput::default())
        }
    }

    #[test]
    fn test_registry_register_and_get() {
        let mut registry = PipelineRegistry::new_empty();
        registry.register(std::sync::Arc::new(DummyPipeline));
        assert!(registry.get("dummy").is_some());
        assert!(registry.get("nonexistent").is_none());
    }

    #[test]
    fn test_registry_list() {
        let mut registry = PipelineRegistry::new_empty();
        registry.register(std::sync::Arc::new(DummyPipeline));
        let names = registry.list();
        assert!(names.contains(&"dummy"));
    }

    #[test]
    fn test_validate_empty_input() {
        let pipeline = DummyPipeline;
        let input = PipelineInput {
            job_id: "test".to_string(),
            import_batch_id: 1,
            org_id: None,
            domain: "science".to_string(),
            publications: vec![],
            options: Default::default(),
        };
        assert!(pipeline.validate(&input).is_err());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd engine && cargo test pipelines::tests`
Expected: FAIL — Pipeline trait not defined

- [ ] **Step 3: Implement Pipeline trait + Registry**

```rust
// engine/src/pipelines/mod.rs
pub mod graph;
pub mod text_analysis;

use std::collections::HashMap;
use std::sync::Arc;
use async_trait::async_trait;

#[derive(Debug, Clone)]
pub struct PipelineInput {
    pub job_id: String,
    pub import_batch_id: i64,
    pub org_id: Option<i64>,
    pub domain: String,
    pub publications: Vec<crate::proto::Publication>,
    pub options: HashMap<String, String>,
}

#[derive(Debug, Default, Clone)]
pub struct PipelineOutput {
    pub nodes_created: i32,
    pub nodes_deduplicated: i32,
    pub relationships_created: i32,
    pub relationships_deduplicated: i32,
    pub keywords_extracted: i32,
    pub entities_classified: i32,
    pub counters: HashMap<String, i32>,
}

pub struct PipelineContext {
    pub pool: sqlx::PgPool,
    pub config: crate::config::Config,
    pub progress: crate::progress::ProgressTracker,
}

#[derive(Debug, thiserror::Error)]
pub enum PipelineError {
    #[error("validation: {0}")]
    Validation(String),
    #[error("database: {0}")]
    Database(#[from] sqlx::Error),
    #[error("internal: {0}")]
    Internal(String),
}

#[derive(Debug)]
pub enum ValidationError {
    EmptyInput,
}

impl std::fmt::Display for ValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::EmptyInput => write!(f, "empty input"),
        }
    }
}

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

pub struct PipelineRegistry {
    pipelines: HashMap<String, Arc<dyn Pipeline>>,
}

impl PipelineRegistry {
    pub fn new_empty() -> Self {
        Self { pipelines: HashMap::new() }
    }

    pub fn register(&mut self, pipeline: Arc<dyn Pipeline>) {
        self.pipelines.insert(pipeline.name().to_string(), pipeline);
    }

    pub fn get(&self, name: &str) -> Option<Arc<dyn Pipeline>> {
        self.pipelines.get(name).cloned()
    }

    pub fn list(&self) -> Vec<&str> {
        self.pipelines.keys().map(|k| k.as_str()).collect()
    }
}
```

- [ ] **Step 4: Create stub modules to satisfy `mod` declarations**

Create empty files:
- `engine/src/pipelines/graph/mod.rs`
- `engine/src/pipelines/text_analysis/mod.rs`
- `engine/src/progress.rs` (with stub `ProgressTracker`)

- [ ] **Step 5: Run tests**

Run: `cd engine && cargo test pipelines::tests`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add engine/src/pipelines/ engine/src/progress.rs
git commit -m "feat(engine): add Pipeline trait and PipelineRegistry"
```

---

### Task 6: Progress Tracker

**Files:**
- Create: `engine/src/progress.rs`
- Test: inline `#[cfg(test)]`

- [ ] **Step 1: Write progress tracker test**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_progress_update_and_subscribe() {
        let tracker = ProgressTracker::new("job-1".to_string());
        let mut rx = tracker.subscribe();

        tracker.update(0.5, "writing_nodes", "50% done").await;

        let event = rx.recv().await.unwrap();
        assert_eq!(event.progress, 0.5);
        assert_eq!(event.phase, "writing_nodes");
    }

    #[tokio::test]
    async fn test_progress_complete() {
        let tracker = ProgressTracker::new("job-2".to_string());
        tracker.update(1.0, "done", "complete").await;
        // No panic on drop
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd engine && cargo test progress::tests`
Expected: FAIL

- [ ] **Step 3: Implement ProgressTracker**

```rust
// engine/src/progress.rs
use tokio::sync::broadcast;

#[derive(Debug, Clone)]
pub struct ProgressEvent {
    pub job_id: String,
    pub progress: f32,
    pub phase: String,
    pub message: String,
    pub counters: std::collections::HashMap<String, i32>,
}

pub struct ProgressTracker {
    job_id: String,
    tx: broadcast::Sender<ProgressEvent>,
}

impl ProgressTracker {
    pub fn new(job_id: String) -> Self {
        let (tx, _) = broadcast::channel(64);
        Self { job_id, tx }
    }

    pub async fn update(&self, progress: f32, phase: &str, message: &str) {
        let event = ProgressEvent {
            job_id: self.job_id.clone(),
            progress,
            phase: phase.to_string(),
            message: message.to_string(),
            counters: Default::default(),
        };
        let _ = self.tx.send(event);
    }

    pub fn subscribe(&self) -> broadcast::Receiver<ProgressEvent> {
        self.tx.subscribe()
    }
}
```

- [ ] **Step 4: Run tests**

Run: `cd engine && cargo test progress::tests`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/src/progress.rs
git commit -m "feat(engine): add ProgressTracker with broadcast channel"
```

---

### Task 7: Job Manager

**Files:**
- Create: `engine/src/jobs.rs`
- Test: inline `#[cfg(test)]`

- [ ] **Step 1: Write job manager test**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_and_get_job() {
        let mgr = JobManager::new(4);
        let job_id = "test-job-1".to_string();
        mgr.create(&job_id, "graph_materialization");
        let status = mgr.get(&job_id).unwrap();
        assert_eq!(status.pipeline, "graph_materialization");
        assert!(matches!(status.status, JobStatus::Queued));
    }

    #[test]
    fn test_update_job_status() {
        let mgr = JobManager::new(4);
        mgr.create("j1", "graph_materialization");
        mgr.set_running("j1");
        let status = mgr.get("j1").unwrap();
        assert!(matches!(status.status, JobStatus::Running));
    }

    #[test]
    fn test_active_count() {
        let mgr = JobManager::new(4);
        mgr.create("j1", "test");
        mgr.set_running("j1");
        mgr.create("j2", "test");
        mgr.set_running("j2");
        assert_eq!(mgr.active_count(), 2);
    }

    #[test]
    fn test_max_concurrent_exceeded() {
        let mgr = JobManager::new(1);
        mgr.create("j1", "test");
        mgr.set_running("j1");
        assert!(!mgr.can_accept());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd engine && cargo test jobs::tests`
Expected: FAIL

- [ ] **Step 3: Implement JobManager**

```rust
// engine/src/jobs.rs
use dashmap::DashMap;
use std::time::Instant;

#[derive(Debug, Clone)]
pub enum JobStatus {
    Queued,
    Running,
    Completed,
    Failed(String),
}

#[derive(Debug, Clone)]
pub struct JobState {
    pub pipeline: String,
    pub status: JobStatus,
    pub progress: f32,
    pub started_at: Instant,
    pub result: Option<crate::pipelines::PipelineOutput>,
}

pub struct JobManager {
    jobs: DashMap<String, JobState>,
    max_concurrent: usize,
}

impl JobManager {
    pub fn new(max_concurrent: usize) -> Self {
        Self {
            jobs: DashMap::new(),
            max_concurrent,
        }
    }

    pub fn create(&self, job_id: &str, pipeline: &str) {
        self.jobs.insert(job_id.to_string(), JobState {
            pipeline: pipeline.to_string(),
            status: JobStatus::Queued,
            progress: 0.0,
            started_at: Instant::now(),
            result: None,
        });
    }

    pub fn get(&self, job_id: &str) -> Option<JobState> {
        self.jobs.get(job_id).map(|r| r.clone())
    }

    pub fn set_running(&self, job_id: &str) {
        if let Some(mut job) = self.jobs.get_mut(job_id) {
            job.status = JobStatus::Running;
        }
    }

    pub fn set_completed(&self, job_id: &str, result: crate::pipelines::PipelineOutput) {
        if let Some(mut job) = self.jobs.get_mut(job_id) {
            job.status = JobStatus::Completed;
            job.progress = 1.0;
            job.result = Some(result);
        }
    }

    pub fn set_failed(&self, job_id: &str, error: String) {
        if let Some(mut job) = self.jobs.get_mut(job_id) {
            job.status = JobStatus::Failed(error);
        }
    }

    pub fn active_count(&self) -> usize {
        self.jobs.iter()
            .filter(|r| matches!(r.value().status, JobStatus::Running))
            .count()
    }

    pub fn can_accept(&self) -> bool {
        self.active_count() < self.max_concurrent
    }
}
```

- [ ] **Step 4: Run tests**

Run: `cd engine && cargo test jobs::tests`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/src/jobs.rs
git commit -m "feat(engine): add JobManager with DashMap concurrent state"
```

---

## Phase 2: gRPC Server

### Task 8: Router Module

**Files:**
- Create: `engine/src/router.rs`
- Test: inline `#[cfg(test)]`

- [ ] **Step 1: Write router test**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_dispatch_known_pipeline() {
        let registry = PipelineRegistry::new_empty();
        // With real pipelines registered, dispatch should find them
        // For now, test that unknown pipeline returns error
        let router = Router::new(registry);
        assert!(router.get_pipeline("nonexistent").is_none());
    }
}
```

- [ ] **Step 2: Implement Router**

```rust
// engine/src/router.rs
use std::sync::Arc;
use crate::pipelines::{Pipeline, PipelineRegistry};

pub struct Router {
    registry: PipelineRegistry,
}

impl Router {
    pub fn new(registry: PipelineRegistry) -> Self {
        Self { registry }
    }

    pub fn get_pipeline(&self, name: &str) -> Option<Arc<dyn Pipeline>> {
        self.registry.get(name)
    }

    pub fn list_pipelines(&self) -> Vec<&str> {
        self.registry.list()
    }
}
```

- [ ] **Step 3: Run test, verify pass**

Run: `cd engine && cargo test router::tests`

- [ ] **Step 4: Commit**

```bash
git add engine/src/router.rs
git commit -m "feat(engine): add Router for pipeline dispatch"
```

---

### Task 9: gRPC Server Implementation

**Files:**
- Create: `engine/src/server.rs`
- Modify: `engine/src/main.rs`

- [ ] **Step 1: Implement the Engine gRPC service**

Implement `EngineService` struct that holds `Arc<Router>`, `Arc<JobManager>`, `PgPool`, `Config`. Implement all 5 RPCs:

- `process_sync` — validates, gets pipeline, calls `pipeline.process()`, returns `ProcessResponse`
- `process_async` — validates, checks `can_accept()`, spawns tokio task, returns `JobAccepted`
- `get_job_status` — looks up job in `JobManager`, returns `JobStatusResponse`
- `stream_progress` — subscribes to `ProgressTracker` broadcast, yields `ProgressEvent`s
- `health` — returns `HealthResponse` with version, pipeline list, active job count

Include auth token validation via tonic interceptor if `ENGINE_AUTH_TOKEN` is set:

```rust
fn auth_interceptor(config: Arc<Config>) -> impl Fn(tonic::Request<()>) -> Result<tonic::Request<()>, tonic::Status> {
    move |req: tonic::Request<()>| {
        if let Some(expected) = &config.auth_token {
            let token = req.metadata()
                .get("x-engine-token")
                .and_then(|v| v.to_str().ok());
            match token {
                Some(t) if t == expected => Ok(req),
                _ => Err(tonic::Status::unauthenticated("invalid or missing x-engine-token")),
            }
        } else {
            Ok(req) // No auth configured
        }
    }
}
```

Apply in main.rs: `EngineServer::with_interceptor(svc, auth_interceptor(config.clone()))`.

Also handle `RESOURCE_EXHAUSTED` in `process_async`: if `!job_manager.can_accept()`, return `Status::resource_exhausted("max concurrent jobs reached")`.

- [ ] **Step 2: Update main.rs with full server bootstrap**

```rust
// engine/src/main.rs
// All modules are re-exported from lib.rs — import from the library crate
use ukip_engine::{config, db, jobs, pipelines, progress, router, server, proto};

use std::process;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().any(|a| a == "--health-check") {
        // TODO: gRPC health check client
        println!("healthy");
        process::exit(0);
    }

    // Init tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .json()
        .init();

    let config = config::Config::from_env()?;
    let pool = db::pool::create_pool(&config.database_url).await?;
    let job_manager = std::sync::Arc::new(jobs::JobManager::new(config.max_concurrent_jobs));

    // Build pipeline registry
    let registry = pipelines::PipelineRegistry::new_empty();
    // TODO: register graph + text_analysis pipelines

    let router = std::sync::Arc::new(router::Router::new(registry));

    let addr = format!("0.0.0.0:{}", config.grpc_port).parse()?;
    tracing::info!(%addr, "starting ukip-engine");

    let svc = server::EngineService::new(router, job_manager, pool, config);

    tonic::transport::Server::builder()
        .add_service(proto::engine_server::EngineServer::new(svc))
        .serve(addr)
        .await?;

    Ok(())
}
```

- [ ] **Step 3: Add graceful shutdown handling**

In `main.rs`, wrap the tonic server with tokio signal handling:

```rust
let (shutdown_tx, shutdown_rx) = tokio::sync::oneshot::channel::<()>();

// Spawn signal handler
tokio::spawn(async move {
    tokio::signal::ctrl_c().await.ok();
    tracing::info!("received shutdown signal");
    let _ = shutdown_tx.send(());
});

tonic::transport::Server::builder()
    .add_service(proto::engine_server::EngineServer::new(svc))
    .serve_with_shutdown(addr, async { shutdown_rx.await.ok(); })
    .await?;

// After server stops: mark in-flight jobs as failed, close DB pool
job_manager.fail_all_active("engine shutdown");
pool.close().await;
```

Add `fail_all_active()` method to `JobManager` in `jobs.rs`:

```rust
pub fn fail_all_active(&self, error: &str) {
    for mut entry in self.jobs.iter_mut() {
        if matches!(entry.value().status, JobStatus::Running | JobStatus::Queued) {
            entry.value_mut().status = JobStatus::Failed(error.to_string());
        }
    }
}
```

- [ ] **Step 4: Verify it compiles**

Run: `cd engine && cargo check`
Expected: Compiles successfully

- [ ] **Step 5: Commit**

```bash
git add engine/src/server.rs engine/src/main.rs engine/src/jobs.rs
git commit -m "feat(engine): implement gRPC server with all 5 RPCs and graceful shutdown"
```

---

## Phase 3: Graph Materialization Pipeline

### Task 10: Canonical ID Generation

**Files:**
- Create: `engine/src/pipelines/graph/canonical.rs`
- Modify: `engine/src/pipelines/graph/mod.rs` — add `pub mod canonical;`
- Test: inline `#[cfg(test)]`

> **Note:** Each subsequent task in this phase (11-14) must also add its `pub mod <name>;` declaration to `engine/src/pipelines/graph/mod.rs`. Similarly, Tasks 16-19 must add declarations to `engine/src/pipelines/text_analysis/mod.rs`.

- [ ] **Step 1: Add mod declaration to graph/mod.rs**

In `engine/src/pipelines/graph/mod.rs`, add:
```rust
pub mod canonical;
pub mod nodes;        // added in Task 11
pub mod relationships; // added in Task 12
pub mod dedup;        // added in Task 14
```
(Add each line as the corresponding file is created in its task.)

- [ ] **Step 2: Write canonical ID tests**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_author_canonical_with_orcid() {
        let author = proto::Author {
            name: "Alice Smith".into(),
            orcid: Some("0000-0001-0000-0001".into()),
            external_id: Some("A1".into()),
            ..Default::default()
        };
        assert_eq!(author_canonical_id(&author), "orcid:0000-0001-0000-0001");
    }

    #[test]
    fn test_author_canonical_with_external_id() {
        let author = proto::Author {
            name: "Bob Jones".into(),
            external_id: Some("https://openalex.org/A123".into()),
            ..Default::default()
        };
        assert_eq!(author_canonical_id(&author), "author:https://openalex.org/A123");
    }

    #[test]
    fn test_author_canonical_name_only() {
        let author = proto::Author {
            name: "Dr. María García-López".into(),
            ..Default::default()
        };
        assert_eq!(author_canonical_id(&author), "author:dr-mar-a-garc-a-l-pez");
    }

    #[test]
    fn test_slug_normalization() {
        assert_eq!(slug("Hello  World!!"), "hello-world");
        assert_eq!(slug("  spaces  "), "spaces");
        assert_eq!(slug("café résumé"), "cafe-resume");
    }

    #[test]
    fn test_concept_canonical_id() {
        assert_eq!(concept_canonical_id("Machine Learning"), "concept:machine-learning");
    }

    #[test]
    fn test_journal_canonical_id() {
        assert_eq!(journal_canonical_id("Nature Reviews"), "journal:nature-reviews");
    }

    #[test]
    fn test_affiliation_canonical_with_external_id() {
        let aff = proto::Affiliation {
            name: "MIT".into(),
            external_id: Some("https://openalex.org/I1".into()),
            ..Default::default()
        };
        assert_eq!(affiliation_canonical_id(&aff), "affiliation:https://openalex.org/I1");
    }

    #[test]
    fn test_affiliation_canonical_name_only() {
        let aff = proto::Affiliation {
            name: "MIT".into(),
            ..Default::default()
        };
        assert_eq!(affiliation_canonical_id(&aff), "affiliation:mit");
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd engine && cargo test pipelines::graph::canonical::tests`

- [ ] **Step 4: Implement canonical ID functions**

```rust
// engine/src/pipelines/graph/canonical.rs
use regex::Regex;
use std::sync::LazyLock;

static SLUG_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[^a-z0-9]+").unwrap());

pub fn slug(value: &str) -> String {
    use unicode_normalization::UnicodeNormalization;
    // NFD decompose then strip combining marks (diacritics) before lowercasing
    let normalized: String = value
        .nfd()
        .filter(|c| !unicode_normalization::char::is_combining_mark(*c))
        .collect();
    let lower = normalized.to_lowercase();
    let slugged = SLUG_RE.replace_all(&lower, "-");
    slugged.trim_matches('-').to_string()
}

pub fn author_canonical_id(author: &crate::proto::Author) -> String {
    if let Some(orcid) = &author.orcid {
        if !orcid.is_empty() {
            return format!("orcid:{orcid}");
        }
    }
    if let Some(ext) = &author.external_id {
        if !ext.is_empty() {
            return format!("author:{ext}");
        }
    }
    format!("author:{}", slug(&author.name))
}

pub fn affiliation_canonical_id(aff: &crate::proto::Affiliation) -> String {
    if let Some(ext) = &aff.external_id {
        if !ext.is_empty() {
            return format!("affiliation:{ext}");
        }
    }
    format!("affiliation:{}", slug(&aff.name))
}

pub fn journal_canonical_id(source_title: &str) -> String {
    format!("journal:{}", slug(source_title))
}

pub fn concept_canonical_id(concept: &str) -> String {
    format!("concept:{}", slug(concept))
}

pub fn identifier_canonical_id(scheme: &str, value: &str) -> String {
    format!("{scheme}:{value}")
}
```

- [ ] **Step 5: Run tests**

Run: `cd engine && cargo test pipelines::graph::canonical::tests`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add engine/src/pipelines/graph/canonical.rs engine/src/pipelines/graph/mod.rs
git commit -m "feat(engine): add canonical ID generation for graph nodes"
```

---

### Task 11: Node Extraction

**Files:**
- Create: `engine/src/pipelines/graph/nodes.rs`
- Test: inline `#[cfg(test)]`

- [ ] **Step 1: Write node extraction tests**

Test that `extract_nodes()` takes a `Publication` and returns a `Vec<PendingNode>` with the correct entity types: author, affiliation, journal, concept, identifier. Test dedup within a single publication (e.g., two authors at same affiliation → one affiliation node).

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement extract_nodes**

The function iterates over a Publication's authors, affiliations, concepts, identifiers, and source_title to produce `PendingNode` structs with correct canonical_ids and entity_types.

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add engine/src/pipelines/graph/nodes.rs
git commit -m "feat(engine): add node extraction from publications"
```

---

### Task 12: Relationship Computation

**Files:**
- Create: `engine/src/pipelines/graph/relationships.rs`
- Test: inline `#[cfg(test)]`

- [ ] **Step 1: Write relationship tests**

Test all 6 relationship types from the spec: authored-by, belongs-to, published-in, has-concept, identified-by, coauthor-with. Verify coauthor pairs are ordered by canonical_id ascending. Verify correct weights.

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement compute_relationships**

```rust
pub fn compute_relationships(
    entity_id: i64,
    pub_canonical_id: &str,
    publication: &Publication,
    org_id: Option<i64>,
) -> Vec<PendingRelationship> { ... }
```

Include coauthor pair generation: for N authors, generate N*(N-1)/2 pairs sorted by canonical_id.

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add engine/src/pipelines/graph/relationships.rs
git commit -m "feat(engine): add relationship computation with coauthor pairs"
```

---

### Task 13: Bulk Writer

**Files:**
- Create: `engine/src/db/bulk_writer.rs`
- Test: `engine/tests/test_bulk_writer.rs` (integration, requires `#[cfg(feature = "integration")]`)

- [ ] **Step 1: Write bulk writer integration test**

```rust
// engine/tests/test_bulk_writer.rs
#![cfg(feature = "integration")]

use ukip_engine::db::bulk_writer::BulkWriter;
use ukip_engine::db::schema::{PendingNode, PendingRelationship};

#[tokio::test]
async fn test_flush_nodes_inserts_and_returns_ids() {
    let pool = test_pool().await;
    let writer = BulkWriter::new(pool.clone(), 100, 100);

    let nodes = vec![
        PendingNode {
            org_id: None,
            import_batch_id: Some(1),
            domain: "science".into(),
            entity_type: "author".into(),
            primary_label: "Alice Smith".into(),
            secondary_label: None,
            canonical_id: "author:alice-smith".into(),
            attributes_json: "{}".into(),
            source: "graph_materializer".into(),
            enrichment_source: None,
            enrichment_concepts: None,
        },
    ];

    let id_map = writer.flush_nodes(&nodes).await.unwrap();
    assert!(id_map.contains_key("author:alice-smith"));
}

#[tokio::test]
async fn test_flush_nodes_dedup_on_conflict() {
    let pool = test_pool().await;
    let writer = BulkWriter::new(pool.clone(), 100, 100);

    let node = PendingNode { /* same as above */ };
    let nodes = vec![node.clone()];

    let map1 = writer.flush_nodes(&nodes).await.unwrap();
    let map2 = writer.flush_nodes(&nodes).await.unwrap();

    // Same canonical_id -> same DB id
    assert_eq!(map1["author:alice-smith"], map2["author:alice-smith"]);
}
```

- [ ] **Step 2: Implement BulkWriter**

```rust
// engine/src/db/bulk_writer.rs
use std::collections::HashMap;
use sqlx::PgPool;
use crate::db::schema::{PendingNode, PendingRelationship, InsertedNode};

pub struct BulkWriter {
    pool: PgPool,
    node_chunk_size: usize,
    rel_chunk_size: usize,
}

impl BulkWriter {
    pub fn new(pool: PgPool, node_chunk_size: usize, rel_chunk_size: usize) -> Self {
        Self { pool, node_chunk_size, rel_chunk_size }
    }

    pub async fn flush_nodes(
        &self,
        nodes: &[PendingNode],
    ) -> Result<HashMap<String, i64>, sqlx::Error> {
        let mut id_map = HashMap::new();
        for chunk in nodes.chunks(self.node_chunk_size) {
            let inserted = self.insert_node_chunk(chunk).await?;
            for node in inserted {
                id_map.insert(node.canonical_id, node.id);
            }
        }
        Ok(id_map)
    }

    pub async fn flush_relationships(
        &self,
        relationships: &[PendingRelationship],
        id_map: &HashMap<String, i64>,
    ) -> Result<i32, sqlx::Error> {
        let mut count = 0i32;
        for chunk in relationships.chunks(self.rel_chunk_size) {
            count += self.insert_rel_chunk(chunk, id_map).await?;
        }
        Ok(count)
    }

    async fn insert_node_chunk(
        &self,
        chunk: &[PendingNode],
    ) -> Result<Vec<InsertedNode>, sqlx::Error> {
        // Build dynamic INSERT ... VALUES ... ON CONFLICT ... RETURNING id, canonical_id
        // Implementation uses sqlx::query_as with dynamic parameter binding
        todo!("implement chunked insert")
    }

    async fn insert_rel_chunk(
        &self,
        chunk: &[PendingRelationship],
        id_map: &HashMap<String, i64>,
    ) -> Result<i32, sqlx::Error> {
        // Build INSERT ... ON CONFLICT DO NOTHING
        todo!("implement chunked relationship insert")
    }
}
```

- [ ] **Step 3: Implement the actual SQL generation**

Build parameterized multi-row INSERT statements. Use `sqlx::query` with dynamic `$N` parameter binding. Handle `org_id IS NOT DISTINCT FROM` for the ON CONFLICT clause.

- [ ] **Step 4: Run integration tests (requires test Postgres)**

Run: `cd engine && cargo test --features integration test_bulk_writer`
Expected: PASS (requires `TEST_DATABASE_URL` env var pointing to a test PostgreSQL instance)

- [ ] **Step 5: Commit**

```bash
git add engine/src/db/bulk_writer.rs engine/tests/test_bulk_writer.rs
git commit -m "feat(engine): add BulkWriter with chunked INSERT ON CONFLICT"
```

---

### Task 14: Cross-Batch Deduplication

**Files:**
- Create: `engine/src/pipelines/graph/dedup.rs`
- Test: inline `#[cfg(test)]` + `engine/tests/test_dedup.rs`

- [ ] **Step 1: Write dedup unit test**

Test that `resolve_existing()` queries the DB for nodes matching a set of canonical_ids and returns a map of canonical_id → DB id.

- [ ] **Step 2: Implement dedup module**

```rust
pub async fn resolve_existing(
    pool: &PgPool,
    org_id: Option<i64>,
    domain: &str,
    canonical_ids: &[String],
) -> Result<HashMap<String, i64>, sqlx::Error> {
    if canonical_ids.is_empty() {
        return Ok(HashMap::new());
    }
    let rows = sqlx::query_as::<_, InsertedNode>(
        "SELECT id, canonical_id FROM raw_entities
         WHERE org_id IS NOT DISTINCT FROM $1
         AND domain = $2
         AND canonical_id = ANY($3)"
    )
    .bind(org_id)
    .bind(domain)
    .bind(canonical_ids)
    .fetch_all(pool)
    .await?;

    Ok(rows.into_iter().map(|r| (r.canonical_id, r.id)).collect())
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add engine/src/pipelines/graph/dedup.rs engine/tests/test_dedup.rs
git commit -m "feat(engine): add cross-batch deduplication via bulk SELECT"
```

---

### Task 15: GraphMaterializationPipeline — Full Assembly

**Files:**
- Modify: `engine/src/pipelines/graph/mod.rs`
- Test: `engine/tests/test_graph_pipeline.rs`

- [ ] **Step 1: Write graph pipeline integration test**

```rust
#![cfg(feature = "integration")]

#[tokio::test]
async fn test_graph_pipeline_creates_nodes_and_relationships() {
    // Setup: create test DB, insert a publication entity
    // Run: GraphMaterializationPipeline.process()
    // Assert: raw_entities has author/journal/concept nodes
    // Assert: entity_relationships has authored-by, published-in, etc.
}

#[tokio::test]
async fn test_graph_pipeline_dedup_across_batches() {
    // Run pipeline twice with same publications
    // Assert: no duplicate nodes
}
```

- [ ] **Step 2: Implement GraphMaterializationPipeline**

Wire together: canonical.rs, nodes.rs, relationships.rs, dedup.rs, bulk_writer.rs.

```rust
pub struct GraphMaterializationPipeline;

#[async_trait]
impl Pipeline for GraphMaterializationPipeline {
    fn name(&self) -> &'static str { "graph_materialization" }

    async fn process(&self, input: PipelineInput, ctx: &PipelineContext) -> Result<PipelineOutput, PipelineError> {
        // 1. Extract all nodes from all publications -> HashSet<PendingNode>
        // 2. Extract all relationships -> Vec<PendingRelationship>
        // 3. Resolve existing nodes (cross-batch dedup)
        // 4. Flush nodes -> id_map
        // 5. Flush relationships using id_map
        // 6. Return PipelineOutput with counts
    }
}
```

- [ ] **Step 3: Register pipeline in main.rs**

```rust
let mut registry = pipelines::PipelineRegistry::new_empty();
registry.register(Arc::new(pipelines::graph::GraphMaterializationPipeline));
```

- [ ] **Step 4: Run integration tests**

Run: `cd engine && cargo test --features integration test_graph_pipeline`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add engine/src/pipelines/graph/mod.rs engine/tests/test_graph_pipeline.rs engine/src/main.rs
git commit -m "feat(engine): implement GraphMaterializationPipeline with full pipeline"
```

---

## Phase 4: Text Analysis Pipeline

### Task 16: Tokenizer + Stopwords

**Files:**
- Create: `engine/src/pipelines/text_analysis/tokenizer.rs`
- Modify: `engine/src/pipelines/text_analysis/mod.rs` — add submodule declarations
- Test: inline `#[cfg(test)]`

- [ ] **Step 0: Add mod declarations to text_analysis/mod.rs**

```rust
pub mod tokenizer;
pub mod keywords;    // added in Task 17
pub mod classifier;  // added in Task 19
pub mod language;    // added in Task 18
```
(Add each line as the corresponding file is created in its task.)

- [ ] **Step 1: Write tokenizer tests**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tokenize_basic() {
        let tokens = tokenize("Hello, world! This is a test.");
        assert!(tokens.contains(&"hello".to_string()));
        assert!(tokens.contains(&"world".to_string()));
        assert!(tokens.contains(&"test".to_string()));
    }

    #[test]
    fn test_stopwords_removed() {
        let tokens = tokenize("the cat is on the mat");
        assert!(!tokens.contains(&"the".to_string()));
        assert!(!tokens.contains(&"is".to_string()));
        assert!(!tokens.contains(&"on".to_string()));
        assert!(tokens.contains(&"cat".to_string()));
        assert!(tokens.contains(&"mat".to_string()));
    }

    #[test]
    fn test_unicode_handling() {
        let tokens = tokenize("über résumé naïve");
        assert_eq!(tokens.len(), 3);
    }

    #[test]
    fn test_empty_input() {
        assert!(tokenize("").is_empty());
        assert!(tokenize("   ").is_empty());
    }
}
```

- [ ] **Step 2: Implement tokenizer**

Unicode-aware splitting using `unicode-segmentation`, lowercase, stopword removal via embedded list (`include_str!`). Create `engine/src/pipelines/text_analysis/stopwords_en.txt` with standard English stopwords.

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add engine/src/pipelines/text_analysis/tokenizer.rs engine/src/pipelines/text_analysis/stopwords_en.txt
git commit -m "feat(engine): add Unicode-aware tokenizer with stopword removal"
```

---

### Task 17: TF-IDF Keyword Extraction

**Files:**
- Create: `engine/src/pipelines/text_analysis/keywords.rs`
- Test: inline `#[cfg(test)]`

- [ ] **Step 1: Write TF-IDF tests**

Test that given a corpus of documents, `extract_keywords()` returns top-N keywords per document with correct ranking. Test min_df / max_df filtering. Test single-document edge case.

- [ ] **Step 2: Implement TF-IDF**

```rust
pub struct TfIdfExtractor {
    max_keywords: usize,
    min_df: f64,
    max_df: f64,
}

impl TfIdfExtractor {
    pub fn new(max_keywords: usize, min_df: f64, max_df: f64) -> Self { ... }

    pub fn extract(&self, corpus: &[Vec<String>]) -> Vec<Vec<(String, f64)>> {
        // 1. Build document frequency map
        // 2. Filter by min_df, max_df
        // 3. Calculate TF-IDF per document
        // 4. Return top-N keywords per document
    }
}
```

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add engine/src/pipelines/text_analysis/keywords.rs
git commit -m "feat(engine): add TF-IDF keyword extraction"
```

---

### Task 18: Language Detection

**Files:**
- Create: `engine/src/pipelines/text_analysis/language.rs`
- Test: inline `#[cfg(test)]`

- [ ] **Step 1: Write language detection tests**

Test detection of EN, ES, FR, DE, PT with known text samples. Test short text fallback. Test unknown language returns None.

- [ ] **Step 2: Implement trigram-based detector**

Pre-computed trigram profiles for supported languages. Compare input text's trigram distribution against profiles. Return highest-scoring language above threshold.

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add engine/src/pipelines/text_analysis/language.rs
git commit -m "feat(engine): add trigram-based language detection"
```

---

### Task 19: Entity Type Classifier

**Files:**
- Create: `engine/src/pipelines/text_analysis/classifier.rs`
- Test: inline `#[cfg(test)]`

- [ ] **Step 1: Write classifier tests**

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_arxiv_preprint_by_doi() {
        let result = classify("10.48550/arXiv.2301.00001", None, None);
        assert_eq!(result.entity_type, "preprint");
        assert!(result.confidence >= 0.9);
    }

    #[test]
    fn test_conference_paper() {
        let result = classify(None, Some("Proceedings of ACL 2024"), None);
        assert_eq!(result.entity_type, "conference_paper");
    }

    #[test]
    fn test_no_source_no_publisher_is_preprint() {
        let result = classify(None, None, None);
        assert_eq!(result.entity_type, "preprint");
        assert!(result.confidence >= 0.6);
    }
}
```

- [ ] **Step 2: Implement rule-based classifier**

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

```bash
git add engine/src/pipelines/text_analysis/classifier.rs
git commit -m "feat(engine): add rule-based entity type classifier"
```

---

### Task 20: TextAnalysisPipeline Assembly

**Files:**
- Modify: `engine/src/pipelines/text_analysis/mod.rs`
- Test: `engine/tests/test_text_pipeline.rs`

- [ ] **Step 1: Write text pipeline integration test**

Test that the pipeline tokenizes abstracts, extracts keywords, detects language, classifies entities, and writes results to DB via batch UPDATE.

- [ ] **Step 2: Implement TextAnalysisPipeline**

Wire together tokenizer, keywords, language, classifier. Write results with batch UPDATE using `unnest` arrays.

- [ ] **Step 3: Register pipeline in main.rs**

- [ ] **Step 4: Run integration tests**

- [ ] **Step 5: Commit**

```bash
git add engine/src/pipelines/text_analysis/ engine/tests/test_text_pipeline.rs engine/src/main.rs
git commit -m "feat(engine): implement TextAnalysisPipeline with TF-IDF + language detection"
```

---

## Phase 5: FastAPI Integration

### Task 21: Engine gRPC Client (Python)

**Files:**
- Create: `backend/services/engine_client.py`
- Test: `tests/test_engine_client.py`

- [ ] **Step 1: Write engine client test**

```python
# tests/test_engine_client.py
"""Tests for engine gRPC client."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.services.engine_client import EngineClient


@pytest.mark.asyncio
async def test_health_returns_false_when_no_connection():
    client = EngineClient(grpc_url="", auth_token="test")
    result = await client.health()
    assert result is False


@pytest.mark.asyncio
async def test_health_returns_false_on_grpc_error():
    client = EngineClient(grpc_url="localhost:99999", auth_token="test")
    result = await client.health()
    assert result is False


@pytest.mark.asyncio
async def test_process_sync_builds_correct_request():
    client = EngineClient(grpc_url="localhost:50051", auth_token="test")
    # Mock the gRPC stub
    with patch.object(client, '_stub') as mock_stub:
        mock_stub.ProcessSync = AsyncMock(return_value=MagicMock(
            status=3,  # COMPLETED
            result=MagicMock(nodes_created=5, relationships_created=10),
        ))
        result = await client.process_sync(
            pipeline="graph_materialization",
            job_id="test-job",
            import_batch_id=1,
            domain="science",
            publications=[],
        )
        assert result is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_engine_client.py -v`

- [ ] **Step 3: Implement EngineClient**

```python
# backend/services/engine_client.py
"""Async gRPC client for the Rust engine."""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EngineClient:
    """Wraps gRPC calls to ukip-engine."""

    def __init__(self, grpc_url: str, auth_token: str = ""):
        self.grpc_url = grpc_url
        self.auth_token = auth_token
        self._channel = None
        self._stub = None

    async def _ensure_channel(self):
        if not self.grpc_url:
            return False
        if self._channel is None:
            try:
                import grpc.aio
                self._channel = grpc.aio.insecure_channel(self.grpc_url)
                # Import generated stubs
                from backend.proto import engine_pb2_grpc
                self._stub = engine_pb2_grpc.EngineStub(self._channel)
            except Exception as e:
                logger.warning("Failed to connect to engine: %s", e)
                return False
        return True

    async def health(self) -> bool:
        if not await self._ensure_channel():
            return False
        try:
            from backend.proto import engine_pb2
            resp = await self._stub.Health(
                engine_pb2.HealthRequest(),
                metadata=[("x-engine-token", self.auth_token)],
                timeout=5,
            )
            return resp.healthy
        except Exception as e:
            logger.debug("Engine health check failed: %s", e)
            return False

    async def process_sync(self, pipeline: str, job_id: str,
                           import_batch_id: int, domain: str,
                           publications: list, org_id: int | None = None,
                           options: dict | None = None) -> Any:
        if not await self._ensure_channel():
            return None
        try:
            from backend.proto import engine_pb2
            req = engine_pb2.ProcessRequest(
                pipeline=pipeline,
                job_id=job_id,
                import_batch_id=import_batch_id,
                domain=domain,
                # publications would be converted to proto messages
            )
            if org_id is not None:
                req.org_id = org_id
            resp = await self._stub.ProcessSync(
                req,
                metadata=[("x-engine-token", self.auth_token)],
                timeout=300,
            )
            return resp
        except Exception as e:
            logger.error("Engine process_sync failed: %s", e)
            return None

    async def close(self):
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None
```

- [ ] **Step 4: Run tests, verify pass**

Run: `.venv/Scripts/python -m pytest tests/test_engine_client.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/services/engine_client.py tests/test_engine_client.py
git commit -m "feat: add async gRPC engine client for FastAPI integration"
```

---

### Task 22: Engine Router (FastAPI Endpoints)

**Files:**
- Create: `backend/routers/engine.py`
- Modify: `backend/main.py`
- Test: `tests/test_engine_router.py`

- [ ] **Step 1: Write engine router test**

```python
# tests/test_engine_router.py
"""Tests for engine status endpoints."""
import pytest


class TestEngineHealth:
    def test_engine_health_no_engine(self, client, auth_headers):
        """When engine is not configured, returns disabled status."""
        resp = client.get("/engine/health", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["engine_available"] is False

    def test_engine_job_not_found(self, client, auth_headers):
        resp = client.get("/engine/jobs/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404
```

- [ ] **Step 2: Implement engine router**

```python
# backend/routers/engine.py
from fastapi import APIRouter, Depends, HTTPException, Request
from backend.auth import get_current_user

router = APIRouter(prefix="/engine", tags=["engine"])

@router.get("/health")
async def engine_health(request: Request, _=Depends(get_current_user)):
    engine = getattr(request.app.state, "engine_client", None)
    if not engine:
        return {"engine_available": False, "message": "Engine not configured"}
    healthy = await engine.health()
    return {"engine_available": healthy}

@router.get("/jobs/{job_id}")
async def engine_job_status(job_id: str, request: Request, _=Depends(get_current_user)):
    engine = getattr(request.app.state, "engine_client", None)
    if not engine:
        raise HTTPException(404, "Engine not configured")
    # TODO: call engine.get_job_status(job_id)
    raise HTTPException(404, f"Job {job_id} not found")
```

- [ ] **Step 3: Include router in main.py**

Add `from backend.routers import engine as engine_router` and `app.include_router(engine_router.router)`.

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_engine_router.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/routers/engine.py tests/test_engine_router.py backend/main.py
git commit -m "feat: add engine health and job status endpoints"
```

---

### Task 23: Ingest Router Engine Integration

**Files:**
- Modify: `backend/routers/ingest.py`
- Test: `tests/test_engine_integration.py`

- [ ] **Step 1: Write engine fallback test**

```python
# tests/test_engine_integration.py
"""Tests for engine integration in ingest pipeline."""
import pytest
from unittest.mock import AsyncMock, patch


class TestEngineIntegration:
    def test_upload_works_without_engine(self, client, auth_headers):
        """Upload still works when engine is not available (Python fallback)."""
        # Upload a small CSV file
        csv_content = "title,doi\nTest Paper,10.1234/test\n"
        files = {"file": ("test.csv", csv_content, "text/csv")}
        resp = client.post("/upload", files=files, headers=auth_headers)
        assert resp.status_code == 201
```

- [ ] **Step 2: Modify ingest.py to try engine first**

In the scientific import path of `upload_file()`, after entities are persisted:

```python
# Try engine for graph materialization
engine = request.app.state.engine_client if hasattr(request.app.state, 'engine_client') else None
if engine and await engine.health():
    try:
        result = await engine.process_sync(
            pipeline="graph_materialization",
            job_id=str(uuid.uuid4()),
            import_batch_id=batch_id,
            domain=domain_id,
            publications=publications_proto,
        )
        if result and result.status == 3:  # COMPLETED
            logger.info("Engine graph materialization: %s nodes, %s rels",
                       result.result.nodes_created, result.result.relationships_created)
        else:
            # Fallback to Python
            materialize_scientific_import_graph(...)
    except Exception as e:
        logger.warning("Engine failed, falling back to Python: %s", e)
        materialize_scientific_import_graph(...)
else:
    materialize_scientific_import_graph(...)
```

- [ ] **Step 3: Initialize engine_client in lifespan (main.py)**

```python
# In lifespan function
engine_url = os.environ.get("ENGINE_GRPC_URL", "")
engine_token = os.environ.get("ENGINE_AUTH_TOKEN", "")
if engine_url:
    from backend.services.engine_client import EngineClient
    app.state.engine_client = EngineClient(engine_url, engine_token)
else:
    app.state.engine_client = None
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_engine_integration.py -v`

- [ ] **Step 5: Run full test suite to ensure no regressions**

Run: `.venv/Scripts/python -m pytest --tb=short -q`
Expected: All existing tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/routers/ingest.py backend/main.py tests/test_engine_integration.py
git commit -m "feat: integrate engine into ingest pipeline with Python fallback"
```

---

## Phase 6: Infrastructure

### Task 24: Dockerfile

**Files:**
- Create: `engine/Dockerfile`

- [ ] **Step 1: Write multi-stage Dockerfile**

```dockerfile
# Build stage
FROM rust:1.82-slim AS builder

RUN apt-get update && apt-get install -y protobuf-compiler pkg-config libssl-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY Cargo.toml Cargo.lock* ./
# Cache dependencies
RUN mkdir src && echo 'fn main() {}' > src/main.rs && cargo build --release && rm -rf src

COPY . .
RUN cargo build --release

# Runtime stage
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/engine /app/engine
WORKDIR /app
ENTRYPOINT ["/app/engine"]
```

- [ ] **Step 2: Verify Docker build**

Run: `cd engine && docker build -t ukip-engine:dev .`
Expected: Successful build

- [ ] **Step 3: Commit**

```bash
git add engine/Dockerfile
git commit -m "feat(engine): add multi-stage Dockerfile"
```

---

### Task 25: Docker Compose Integration

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add ukip-engine service to docker-compose.yml**

Add the service definition from spec Section 9 (Docker Compose Addition). Include depends_on postgres with health check condition. Set environment variables. Do NOT publish port 50051 to host.

- [ ] **Step 2: Add ENGINE_GRPC_URL to ukip-backend service**

```yaml
ukip-backend:
  environment:
    ENGINE_GRPC_URL: ukip-engine:50051
    ENGINE_AUTH_TOKEN: ${ENGINE_AUTH_TOKEN:-dev-secret}
    ENGINE_SYNC_THRESHOLD: "500"
    ENGINE_SHADOW_MODE: "false"
    ENGINE_FALLBACK_PYTHON: "true"
```

- [ ] **Step 3: Test docker compose config**

Run: `docker compose config`
Expected: Valid YAML, no errors

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add ukip-engine to Docker Compose"
```

---

### Task 26: Python Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add gRPC dependencies**

Add to requirements.txt:
```
grpcio>=1.62.0
grpcio-tools>=1.62.0
protobuf>=4.25.0
```

- [ ] **Step 2: Install and verify**

Run: `.venv/Scripts/pip install grpcio grpcio-tools protobuf`

- [ ] **Step 3: Generate Python proto stubs**

```bash
mkdir -p backend/proto/ukip/engine/v1
python -m grpc_tools.protoc \
  -Iengine/proto \
  --python_out=backend/proto \
  --grpc_python_out=backend/proto \
  engine/proto/ukip/engine/v1/engine.proto
touch backend/proto/__init__.py
touch backend/proto/ukip/__init__.py
touch backend/proto/ukip/engine/__init__.py
touch backend/proto/ukip/engine/v1/__init__.py
```

> **Note:** Proto stubs will be generated at `backend/proto/ukip/engine/v1/engine_pb2.py` and `engine_pb2_grpc.py`. Update imports in `engine_client.py` accordingly: `from backend.proto.ukip.engine.v1 import engine_pb2, engine_pb2_grpc`.

- [ ] **Step 4: Update .env.example with engine variables**

Add to `.env.example`:
```bash
# Engine (Rust) — only needed when running ukip-engine container
ENGINE_DATABASE_URL=postgresql://ukip:ukip_secret@postgres:5432/ukip
ENGINE_GRPC_PORT=50051
ENGINE_LOG_LEVEL=info
ENGINE_AUTH_TOKEN=change-me-in-production
ENGINE_MAX_CONCURRENT_JOBS=4

# FastAPI — engine integration
ENGINE_GRPC_URL=                    # empty = engine disabled
ENGINE_SYNC_THRESHOLD=500
ENGINE_SHADOW_MODE=false
ENGINE_FALLBACK_PYTHON=true
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt backend/proto/
git commit -m "feat: add gRPC Python dependencies and generated proto stubs"
```

---

## Phase 7: Benchmarks

### Task 27: Criterion Benchmarks

**Files:**
- Create: `engine/benches/graph_materialization.rs`
- Create: `engine/benches/text_analysis.rs`

- [ ] **Step 1: Write graph materialization benchmark**

```rust
use criterion::{criterion_group, criterion_main, Criterion, BenchmarkId};

fn bench_graph_pipeline(c: &mut Criterion) {
    let mut group = c.benchmark_group("graph_materialization");
    for size in [1000, 2841, 10000] {
        group.bench_with_input(
            BenchmarkId::from_parameter(size),
            &size,
            |b, &size| {
                // Generate `size` test publications
                // Benchmark the in-memory phase only (node extraction + dedup)
                b.iter(|| {
                    // extract_all_nodes + compute_all_relationships
                });
            },
        );
    }
    group.finish();
}

criterion_group!(benches, bench_graph_pipeline);
criterion_main!(benches);
```

- [ ] **Step 2: Write text analysis benchmark**

Similar structure for TF-IDF extraction over varying corpus sizes.

- [ ] **Step 3: Run benchmarks**

Run: `cd engine && cargo bench`

- [ ] **Step 4: Commit**

```bash
git add engine/benches/
git commit -m "feat(engine): add criterion benchmarks for pipelines"
```

---

## Phase 8: Shadow Mode (Future — Post-MVP)

### Task 28: Shadow Mode Implementation

> **Note:** This task is deferred until the engine is deployed and stable. It involves:
> - Creating shadow tables in a migration
> - Adding `ENGINE_SHADOW_MODE` env var handling in the Python client
> - Running both Python + Rust pipelines and comparing results
> - Logging discrepancies with `expected_dedup_delta`
> - Graduation criteria: 20 consecutive imports with 0 discrepancies

- [ ] **Step 1: Design shadow table migration**
- [ ] **Step 2: Implement shadow mode comparator in Python**
- [ ] **Step 3: Add shadow mode toggle to engine client**
- [ ] **Step 4: Write shadow mode integration tests**
- [ ] **Step 5: Commit**

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Phase 0 | Task 1 | PostgreSQL prerequisites (migration) |
| Phase 1 | Tasks 2-7 | Rust scaffolding: Cargo, proto, config, DB, pipeline trait, progress, jobs |
| Phase 2 | Tasks 8-9 | gRPC server: router, server impl |
| Phase 3 | Tasks 10-15 | Graph materialization: canonical IDs, nodes, relationships, bulk writer, dedup, pipeline |
| Phase 4 | Tasks 16-20 | Text analysis: tokenizer, TF-IDF, language detection, classifier, pipeline |
| Phase 5 | Tasks 21-23 | FastAPI integration: gRPC client, engine router, ingest integration |
| Phase 6 | Tasks 24-26 | Infrastructure: Dockerfile, docker-compose, Python deps |
| Phase 7 | Task 27 | Benchmarks |
| Phase 8 | Task 28 | Shadow mode (deferred) |

**Total:** 28 tasks, ~120 steps
