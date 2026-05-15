## 1. Rust CRITICAL Fixes

- [x] 1.1 Define `ALLOWED_COLUMNS` whitelist in `engine/src/pipelines/analytics/mod.rs` with all known RawEntity column names (primary_label, secondary_label, entity_type, enrichment_concepts, etc.)
- [x] 1.2 In `load_field_data`, validate each field_filter against `ALLOWED_COLUMNS` before SQL construction — return `PipelineError::Validation` for unknown columns
- [x] 1.3 Replace `assert_eq!(x.len(), y.len())` in `engine/src/pipelines/analytics/correlation.rs` with `if x.len() != y.len() { return Err(...) }`
- [x] 1.4 Write tests: analytics with invalid field_filter → verify Validation error returned, not SQL error

## 2. Rust HIGH Fixes — Panic Elimination

- [x] 2.1 Replace `unreachable!("validated above")` in `engine/src/pipelines/analytics/mod.rs:135` with `Err(PipelineError::Validation(format!("unknown analytics mode: {}", mode)))`
- [x] 2.2 Replace `unreachable!("validated above")` in `engine/src/pipelines/normalization/mod.rs:107` (or equivalent line) with `Err(PipelineError::Validation(...))`
- [x] 2.3 Add input size validation in `ConnectorPipeline::validate()`: reject `queries.len() > 200`
- [x] 2.4 Add input size validation in `DisambiguationPipeline::validate()`: reject `values.len() > 50_000`
- [x] 2.5 Add input size validation in `NormalizationPipeline::validate()`: reject `values.len() > 50_000`
- [x] 2.6 Write tests: oversized inputs → verify Validation error for each pipeline

## 3. Rust HIGH Fixes — Infrastructure

- [x] 3.1 Add SIGTERM handler in `engine/src/main.rs` using `tokio::signal::unix::signal(SignalKind::terminate())` with `cfg(unix)` guard, combined with existing Ctrl-C via `tokio::select!`
- [x] 3.2 Add pool timeouts in `engine/src/db/pool.rs`: `acquire_timeout(5s)`, `idle_timeout(600s)`, `max_lifetime(1800s)`, `min_connections(2)`
- [x] 3.3 Replace `can_accept()` + `create()` TOCTOU pattern in `engine/src/server.rs` with `tokio::sync::Semaphore` — `try_acquire()` returns permit or `Status::resource_exhausted`
- [x] 3.4 Add `[profile.release]` to `engine/Cargo.toml`: `opt-level = 3`, `lto = "thin"`, `codegen-units = 1`, `strip = true`
- [x] 3.5 Add `tracing::warn!` at engine startup if `auth_token` is `None`
- [x] 3.6 Run `cargo clippy` and `cargo test` — zero warnings, all tests pass

## 4. Python CRITICAL Fixes

- [x] 4.1 Add conditional TLS in `backend/services/engine_client.py`: check `ENGINE_GRPC_TLS` env var — if `"1"` use `grpc.aio.secure_channel(url, grpc.ssl_channel_credentials())`, else `insecure_channel`
- [x] 4.2 Log warning at `_ensure_channel` if TLS disabled and URL is not `localhost`/`127.0.0.1`
- [x] 4.3 Remove `api_key: Optional[str] = None` from `AIResolveRequest` in `backend/routers/disambiguation.py`
- [x] 4.4 Update `resolve_canonical_name` call to not pass `api_key` parameter

## 5. Python HIGH Fixes — Input Validation

- [x] 5.1 Add `_sanitize_job_id(raw: str) -> str` in `engine_client.py` — strip non-`[a-zA-Z0-9_-]`, truncate to 128 chars — apply to all `job_id=f"..."` constructions
- [x] 5.2 Validate `source` in `SearchRequest` and `DoiBatchRequest` against `list_sources()` allowlist — return 400 if invalid
- [x] 5.3 Replace `config: dict` with typed `AdapterConfig` Pydantic model in `SearchRequest` and `DoiBatchRequest` (known keys: `email`, `api_key_name`)
- [x] 5.4 Add `_DOMAIN_RE = re.compile(r"^[a-z][a-z0-9_\-]{0,63}$")` validation in `dashboard_compare` for each domain_id — return 422 if invalid
- [x] 5.5 Add `MAX_DELEGATION_VALUES = 50_000` in `engine_delegation.py` — truncate + warn before engine calls in `try_engine_disambiguation` and `try_engine_normalization`
- [x] 5.6 Change `/engine/health` and `/engine/jobs/{job_id}` to `Depends(require_role("super_admin", "admin"))` in `backend/routers/engine.py`
- [x] 5.7 Write tests: invalid source → 400, invalid domain_id → 422, values over cap → truncated, engine health with viewer → 403

## 6. Verification

- [x] 6.1 Run full Rust test suite: `cargo test` — all pass, 0 clippy warnings
- [x] 6.2 Run full Python test suite: `pytest backend/tests/` — no regressions from changes
- [ ] 6.3 Verify SIGTERM in Docker: `docker compose up`, `docker kill --signal=SIGTERM ukip-engine`, verify clean shutdown in logs
- [x] 6.4 Update `.env.example` with `ENGINE_GRPC_TLS` and `ENGINE_AUTH_TOKEN` documentation
