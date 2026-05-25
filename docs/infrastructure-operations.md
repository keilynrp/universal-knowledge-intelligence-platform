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

## Ports

| Service | Port | Configurable |
|---------|------|--------------|
| FastAPI API | 8000 | Via `uvicorn --port` |
| Next.js Frontend | 3004 | Via `next dev --port` |
| ChromaDB | In-process | N/A |
| DuckDB | In-process | N/A |
| SQLite | File-based | Via `DATABASE_URL` |

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
