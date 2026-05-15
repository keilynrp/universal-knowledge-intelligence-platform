## Why

The Rust engine and Python delegation layer completed implementation and passed functional tests, but a production readiness audit (Rust reviewer + security reviewer + deployment explorer) identified 4 CRITICAL and 13 HIGH issues that block production deployment. These include SQL injection vectors, panic-inducing assertions, plaintext gRPC transport, unbounded inputs enabling DoS, missing SIGTERM handling for Kubernetes, and DB pool misconfiguration. These must be resolved before the engine can serve production traffic.

## What Changes

- Fix SQL injection in analytics `load_field_data` — replace character sanitization with column whitelist
- Replace `assert_eq!` panic in `cramers_v` with `Result::Err`
- Replace `unreachable!()` in analytics and normalization pipelines with proper error returns
- Add conditional TLS support for gRPC channel (`ENGINE_GRPC_TLS` env var)
- **BREAKING**: Remove `api_key` field from `AIResolveRequest`
- Add SIGTERM handler for graceful shutdown in Kubernetes
- Add `acquire_timeout`, `idle_timeout`, `max_lifetime` to DB connection pool
- Fix TOCTOU race in `can_accept` with atomic semaphore
- Add upper bounds on `queries.len()` and `values.len()` in both Rust and Python
- Sanitize job IDs to `[a-zA-Z0-9_\-]{1,128}`
- Validate `source` against allowlist in scientific import endpoints
- Type `config` dict in `SearchRequest`/`DoiBatchRequest` with explicit schema
- Validate `domain_id` in `dashboard_compare` and analytics cache keys
- Add `[profile.release]` to Cargo.toml
- Restrict `/engine/health` to admin+ role

## Capabilities

### New Capabilities
- `rust-safety-hardening`: Eliminate all panic paths (assert_eq, unreachable!), SQL injection whitelist, and unbounded input caps in the Rust engine
- `grpc-transport-security`: TLS support for gRPC channel, job ID sanitization, and auth token protection
- `deployment-hardening`: SIGTERM handler, DB pool timeouts, release profile, concurrent job semaphore
- `python-input-validation`: Source allowlist, config schema validation, domain_id validation, values cap, api_key removal, engine health auth

### Modified Capabilities

## Impact

- **Rust engine**: `engine/src/` — pipelines, server, db, main, Cargo.toml
- **Python backend**: `backend/services/engine_client.py`, `backend/services/engine_delegation.py`, `backend/routers/analytics.py`, `backend/routers/disambiguation.py`, `backend/routers/scientific_import.py`, `backend/routers/engine.py`
- **API breaking change**: `AIResolveRequest.api_key` field removed — clients must stop sending it
- **Deployment**: New env vars `ENGINE_GRPC_TLS`, `ENGINE_AUTH_TOKEN` (warning if unset)
- **Dependencies**: May add `rustls` or `native-tls` to Cargo.toml for gRPC TLS
