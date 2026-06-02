# Infrastructure Operations Architecture

## Deployment Topology

```
                          ┌─────────────────┐
                          │   Next.js App    │
                          │  (port 3004)     │
                          └───────┬─────────┘
                                  │ HTTP
                          ┌───────▼─────────┐
                          │   FastAPI App    │
                          │  (port 8000)     │
                          ├─────────────────┤
                          │  Middleware:     │
                          │  - CORS          │
                          │  - Rate limiter  │
                          │  - Security hdrs │
                          │  - Audit log     │
                          │  - Session       │
                          │  - Request log   │
                          └──┬──┬──┬──┬─────┘
                             │  │  │  │
              ┌──────────────┘  │  │  └──────────────┐
              ▼                 ▼  ▼                  ▼
        ┌──────────┐  ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  SQLite   │  │ ChromaDB │ │  DuckDB  │ │ External │
        │ sql_app.db│  │  (RAG)   │ │  (OLAP)  │ │   APIs   │
        └──────────┘  └──────────┘ └──────────┘ └──────────┘
                                                  OpenAlex
                                                  ORCID
                                                  Wikidata
                                                  VIAF
                                                  ROR
                                                  DBpedia
```

### Background Workers

| Worker | Entry Point | Description |
|--------|-------------|-------------|
| Enrichment worker | `backend/enrichment_worker.py` | Polls pending entities, enriches via external APIs, circuit-breaker protected |
| Enrichment scheduler | `backend/services/enrichment_scheduler.py` | Domain-level enrichment policies on a configurable schedule |
| Scheduled imports | `backend/routers/scheduled_imports.py` | Cron-style import from connected source adapters |
| Scheduled reports | `backend/routers/scheduled_reports.py` | Cron-style report generation with email delivery |

All workers start as `asyncio.create_task()` during app lifespan. They share the same process as the API server.

## Environment Variable Contract

### Required (Production)

| Variable | Purpose | Secret | Default |
|----------|---------|--------|---------|
| `JWT_SECRET_KEY` | JWT token signing | Yes | None (warns on startup) |
| `ENCRYPTION_KEY` | Fernet key for DB credential encryption | Yes | None (warns on startup) |
| `ADMIN_USERNAME` | Bootstrap super_admin username | No | None (warns on startup) |
| `ADMIN_PASSWORD` | Bootstrap super_admin password (first boot only) | Yes | None |
| `ADMIN_PASSWORD_HASH` | Alternative: pre-hashed bcrypt password | Yes | None |

### Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///./sql_app.db` |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | `http://localhost:3004,http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | Frontend API base URL | `http://localhost:8000` |
| `SESSION_SECRET_KEY` | Session cookie signing | Falls back to `JWT_SECRET_KEY` |
| `ENABLE_COMMERCE_ADAPTERS` | Show/hide commerce store types | `true` |
| `ENABLE_LINKED_DATA_EXPORT` | Enable JSON-LD export features | `false` |
| `ENABLE_STAKEHOLDER_DEMO` | Enable stakeholder demo mode | `false` |
| `ENGINE_GRPC_URL` | Rust engine gRPC endpoint | Empty (disabled) |
| `ENGINE_AUTH_TOKEN` | Rust engine auth token | Empty |
| `UKIP_SKIP_STARTUP_SIDE_EFFECTS` | Skip workers/migrations in test | `0` |
| `REDIS_URL` | Distributed cache connection string. Empty ⇒ in-process caches | Empty (in-process) |
| `UKIP_CACHE_PREFIX` | Key namespace prefix (lets multiple deploys share one Redis) | `ukip` |
| `UKIP_CACHE_CONNECT_TIMEOUT` | Redis socket connect timeout (seconds), fail-open | `0.5` |
| `UKIP_CACHE_SOCKET_TIMEOUT` | Redis socket op timeout (seconds), fail-open | `0.5` |

### Startup Guard

The lifespan function validates on startup:
1. Required vars are set (warns if missing)
2. Insecure placeholder values are flagged (`JWT_SECRET_KEY=changeit`, `ADMIN_PASSWORD=admin`, etc.)
3. CORS wildcard (`ALLOWED_ORIGINS=*`) triggers a warning

## Health Check

| Endpoint | Auth | Response |
|----------|------|----------|
| `GET /health` | None | `{"status": "ok"}` |

The health endpoint is always public and does not require authentication. It confirms the API server is responsive. It does not check database connectivity or worker health.

## Distributed Cache (Redis)

UKIP's six internal caches (authority resolver, adaptive thresholds, feedback
priors, derived-status bundles, and the two analytics caches) are backed by a
pluggable cache layer in `backend/cache/`. Backend selection is automatic:

| `REDIS_URL` | Backend | Behavior |
|-------------|---------|----------|
| Empty / unset | `InProcessBackend` (`cachetools`) | Per-process caches. Single-process only — **not** coherent across workers or deploys. This is the default and matches pre-Redis behavior. |
| Set | `RedisBackend` (JSON, `redis-py`) | Cross-worker coherent, survives restarts/deploys. Cache invalidation propagates to every backend instance sharing the Redis. |

### Design properties

- **Fail-open.** Every Redis error is swallowed: reads degrade to a cache miss
  (recompute), writes and invalidations become no-ops. A Redis outage never
  raises into a request handler. Timeouts are kept small (`0.5s`) so a hung
  Redis cannot stall requests.
- **Key namespacing.** All keys are prefixed `${UKIP_CACHE_PREFIX}:<cache>:` so
  multiple deployments can safely share one Redis instance.
- **TTLs preserved per cache** (resolver 7d, thresholds/feedback/analytics 300s,
  dashboard 120s, derived-status 30s). Negative results (e.g. "no threshold
  override") are cached too, so misses don't re-hit the DB.
- **No app-visible API change.** Every cache keeps its original public
  signature; only the storage backend changed.

### Production wiring (Dokploy / Compose)

`docker-compose.prod.yml` ships a co-located `ukip-redis` service
(`redis:7-alpine`, `--maxmemory 256mb --maxmemory-policy allkeys-lru`, no
persistence — cache data is regenerable). `ukip-backend` declares the cache
env vars and `depends_on` redis being healthy. `REDIS_URL` defaults to
`redis://ukip-redis:6379/0` and is overridable from the Dokploy Environment tab
to point at a managed Redis instead.

### Operating

- **Enable:** ensure `REDIS_URL` is set (default points at the in-stack service),
  then redeploy. Confirm the startup log line:
  `Redis cache reachable — distributed cache active`.
  If unset/unreachable you'll see `Redis not configured/reachable — using in-process cache`.
- **Rollback:** set `REDIS_URL=` (empty) in Dokploy and redeploy → in-process caches.
- **Lifespan:** a non-blocking `ping()` runs on startup (log only — never blocks
  boot); the pool is closed on shutdown.
- **Monitoring suggestions:** Redis `INFO` memory/`evicted_keys` (LRU pressure
  ⇒ raise `UKIP_REDIS_MAXMEMORY`), `keyspace_hits`/`keyspace_misses` ratio, and
  connection count. Eviction is expected and safe (every key has a TTL).

## Ports

| Service | Port | Configurable |
|---------|------|--------------|
| FastAPI API | 8000 | Via `uvicorn --port` |
| Next.js Frontend | 3004 | Via `next dev --port` |
| ChromaDB | In-process | N/A |
| DuckDB | In-process | N/A |
| SQLite | File-based | Via `DATABASE_URL` |
| Redis (optional) | 6379 | Via `REDIS_URL`; in-stack `ukip-redis` service, not host-published |

## Operational Metrics

### API Layer
- Request count by endpoint and status code (via request logging middleware)
- Error rate (5xx responses)
- Rate limit rejections (SlowAPI)

### Enrichment Pipeline
- Queue depth: `SELECT COUNT(*) FROM raw_entities WHERE enrichment_status = 'pending'`
- Failure rate: circuit breaker state per provider
- Processing rate: entities enriched per minute

### Database
- SQLite file size monitoring
- Connection pool usage (StaticPool in test, default pool in production)

## Backup and Recovery

### SQLite
- File: `sql_app.db` — single-file database
- Backup: file copy while server is stopped, or `sqlite3 .backup` command
- Recovery: replace the file and restart

### ChromaDB
- Persistent directory (default: `./chroma_data/`)
- Backup: copy the directory
- Can be rebuilt from source entities via `POST /rag/index`

### Rollback Safety
- All enrichment is additive (provenance layering preserves source data)
- Harmonization has undo/redo support
- Authority resolution has reject/rollback per candidate
- Demo mode data tagged with `source="demo"` for clean reset
