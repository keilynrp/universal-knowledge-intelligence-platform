## Context

The Rust engine (`ukip-engine`) serves 6 compute pipelines (authority, analytics, disambiguation, normalization, connectors, graph) over gRPC. The Python FastAPI backend delegates to it with graceful fallback. A production readiness audit found 4 CRITICAL and 13 HIGH issues across both layers. This design addresses all of them.

## Goals / Non-Goals

### Goals
- Eliminate all panic paths in Rust engine (zero `unwrap`/`assert`/`unreachable!` on user data paths)
- Close SQL injection vectors with column whitelists
- Secure gRPC transport with conditional TLS
- Add resource bounds to prevent DoS (input caps, pool timeouts, query limits)
- Make the engine Kubernetes-ready (SIGTERM, health probes, release profile)
- Validate all user-controlled inputs before forwarding to engine

### Non-Goals
- Mutual TLS (mTLS) — deferred to network-level security (service mesh)
- Horizontal scaling / multi-replica engine — separate change
- Comprehensive pen-test — this is targeted fix of known audit findings

## Approach

### Phase 1: Rust Safety (CRITICAL)

**SQL injection whitelist** (`analytics/mod.rs`):
- Define `const ALLOWED_COLUMNS: &[&str]` with the known RawEntity column names
- In `load_field_data`, reject any `field_filter` not in this set before query construction
- Return `PipelineError::Validation` for unknown columns

**`assert_eq!` → Result** (`correlation.rs`):
- Replace `assert_eq!(x.len(), y.len())` with an early `if x.len() != y.len() { return Err(...) }`
- Return `PipelineError::Internal("mismatched column lengths")`

### Phase 2: Rust Stability (HIGH)

**`unreachable!()` elimination**:
- In `AnalyticsPipeline::process` and `NormalizationPipeline::process`, replace `_ => unreachable!()` with `_ => Err(PipelineError::Validation(...))`

**SIGTERM handler** (`main.rs`):
- Add `tokio::signal::unix::signal(SignalKind::terminate())` alongside existing Ctrl-C handler
- Use `tokio::select!` to listen for either signal
- Windows: keep Ctrl-C only (SIGTERM not available)

**DB pool hardening** (`db/pool.rs`):
- Add `.acquire_timeout(Duration::from_secs(5))`
- Add `.idle_timeout(Duration::from_secs(600))`
- Add `.max_lifetime(Duration::from_secs(1800))`
- Add `.min_connections(2)` for connection warmup

**TOCTOU fix** (`server.rs`):
- Replace `can_accept()` + `create()` with `tokio::sync::Semaphore`
- `try_acquire()` returns permit or `Status::resource_exhausted`
- Permit held through job lifetime, dropped on completion

**Unbounded input caps**:
- `ConnectorRequest.queries`: validate `queries.len() <= 200` in `validate()`
- `DisambiguationRequest.values`: validate `values.len() <= 50_000`
- `NormalizationRequest.values`: validate `values.len() <= 50_000`

**Release profile** (`Cargo.toml`):
```toml
[profile.release]
opt-level = 3
lto = "thin"
codegen-units = 1
strip = true
```

### Phase 3: gRPC Transport Security

**Conditional TLS** (`engine_client.py`):
- Check `ENGINE_GRPC_TLS` env var (default: `"0"`)
- If `"1"`: use `grpc.aio.secure_channel` with `ssl_channel_credentials()`
- If `"0"`: use `insecure_channel` (localhost dev only)
- Log warning at startup if TLS is disabled and URL is not localhost

**Job ID sanitization** (`engine_client.py`):
- Add `_sanitize_job_id(raw: str) -> str` that strips non-`[a-zA-Z0-9_-]` and truncates to 128 chars
- Apply to all job_id constructions in convenience methods

### Phase 4: Python Input Validation

**`api_key` removal** (`disambiguation.py`):
- Remove `api_key: Optional[str]` from `AIResolveRequest`
- Update `resolve_canonical_name` call to not pass `api_key`

**Source allowlist** (`scientific_import.py`):
- Add `_VALID_SOURCES = frozenset(s["id"] for s in list_sources())`
- Validate `body.source in _VALID_SOURCES` before dispatching

**Config schema** (`scientific_import.py`):
- Replace `config: dict` with `config: AdapterConfig` Pydantic model
- `AdapterConfig` has only the known keys (e.g., `email: str | None`, `api_key_env: str | None`)

**Domain ID validation** (`analytics.py`):
- Validate each domain_id against `^[a-z][a-z0-9_\-]{0,63}$` in `dashboard_compare`
- Apply same validation to cache key construction

**Values cap** (`engine_delegation.py`):
- Add `MAX_DELEGATION_VALUES = 50_000`
- Truncate values list before sending to engine, log warning if truncated

**Engine health auth** (`engine.py`):
- Change `_=Depends(get_current_user)` to `_=Depends(require_role("super_admin", "admin"))`

## Testing Strategy

- Rust: `cargo test` — existing 179 tests must pass + new tests for whitelist rejection, error returns
- Python: `pytest backend/tests/` — existing suite + new tests for TLS config, input validation, caps
- Clippy: zero warnings required
- Manual: verify SIGTERM works in Docker container
