## Context

The `engine-compute-kernel` change (78 tasks, complete) delivered:
- 6 Rust gRPC compute pipelines: authority, analytics, disambiguation, normalization, connectors
- Python `EngineClient` with convenience methods for each pipeline
- Router-level delegation wired **only for authority** (`backend/routers/authority.py`)

The remaining 4 pipelines have `EngineClient` methods ready but no router-level wiring. Each FastAPI endpoint still runs pure Python even when the Rust engine is available.

Current router structure:
- `analytics.py` — 4 analyzer endpoints (`topics`, `cooccurrence`, `clusters`, `correlation`) using `TopicAnalyzer` / `CorrelationAnalyzer`
- `disambiguation.py` — `GET /disambiguate/{field}` using `_build_disambig_groups` (Python thefuzz)
- `disambiguation.py` — `POST /rules/apply` applying normalization rules row-by-row
- Connectors — Python import adapters (OpenAlex, Crossref, PubMed) in `backend/services/`

## Goals / Non-Goals

**Goals:**
- Delegate analytics, disambiguation, normalization, and connector calls to the Rust engine when available
- Maintain 100% backward compatibility — identical API responses whether served by Rust or Python
- Transparent fallback: if engine is unavailable or returns an error, silently use Python path
- Shared delegation pattern to minimize boilerplate across routers
- Test coverage for both delegation success and fallback paths

**Non-Goals:**
- Changing any API contracts or response schemas
- Modifying the Rust engine or proto definitions (already complete)
- Frontend changes (delegation is invisible to clients)
- Async/job-based delegation (all delegation is synchronous via `ProcessSync`)
- Delegating harmonization steps (these are tightly coupled to SQLAlchemy ORM mutations)

## Decisions

### 1. Shared delegation helper module

**Decision**: Create `backend/services/engine_delegation.py` with a `try_engine_*` pattern.

Each helper:
1. Checks if `engine_client` is available on `request.app.state`
2. Calls the appropriate `EngineClient.process_*` method
3. Converts the proto response to the Python-native format
4. Returns `None` on any failure (signaling fallback)

**Rationale**: The authority delegation in `resolver.py` proved the pattern works. Extracting it to a shared module avoids duplicating try/except/convert logic in every router. The `None`-means-fallback convention is already established.

**Alternative considered**: Middleware-level delegation. Rejected because each endpoint has different input/output shapes and the delegation decision depends on payload size.

### 2. Threshold-based delegation for disambiguation and normalization

**Decision**: Only delegate to engine when dataset size exceeds a threshold (default: 100 values for disambiguation, 100 rules for normalization).

**Rationale**: For small datasets, Python is fast enough and the gRPC round-trip adds latency. The Rust advantage is on large datasets where O(n*w) blocking or bulk regex outperforms Python. This matches task 9.6 spec ("batch-delegate for bulk operations >100 values").

### 3. Analytics delegation sends raw data, not DB queries

**Decision**: The Rust analytics pipeline reads from its own Postgres connection. The Python fallback reads via SQLAlchemy. For delegation, the router just sends `domain_id` + `mode` (topics/cooccurrence/clusters/correlation) and lets the engine query its shared DB.

**Rationale**: The Rust engine already has `load_concepts()` and `load_field_data()` async DB queries in `analytics/mod.rs`. Sending raw data over gRPC would be wasteful when both Python and Rust can query the same Postgres.

### 4. Connector delegation is opt-in via query parameter

**Decision**: Add `?engine=true` query parameter to connector-facing endpoints. Default: use existing Python adapters.

**Rationale**: The Rust connectors have their own rate limiter and retry logic. Running both Python and Rust connectors simultaneously against the same APIs could cause rate limit issues. Making it opt-in avoids surprises.

### 5. Cache integration

**Decision**: Delegation results go through the same `_analytics_cache` / `_SimpleCache` as Python results. The cache key is identical regardless of which backend computed the result.

**Rationale**: Cache-then-delegate means repeated requests are served from cache. First-miss triggers delegation. This is transparent and preserves existing TTL behavior.

## Risks / Trade-offs

- **[Result format mismatch]** → Rust and Python may produce slightly different floating-point results (e.g., PMI scores, Cramér's V). Mitigation: golden-file tests already verify parity within tolerance. Delegation tests will verify response schema compatibility.

- **[Engine DB access]** → Analytics delegation assumes the Rust engine can access the same Postgres with the publications/concepts data. Mitigation: the engine already reads from `ENGINE_DATABASE_URL` which should point to the same DB. Document this as a deployment requirement.

- **[Partial failure]** → If engine is available for health check but fails mid-computation, the fallback kicks in and the user gets Python results with added latency. Mitigation: log a warning on fallback so operators can investigate. The total latency is engine-attempt-timeout + python-compute, but the engine timeout is 30s max.

- **[Threshold tuning]** → The 100-value threshold is a heuristic. Too low = unnecessary gRPC overhead. Too high = missing speedup opportunities. Mitigation: make threshold configurable via environment variable (`ENGINE_DELEGATION_THRESHOLD`).
