# Backend Architecture Codemap

**Last Updated:** 2026-05-20 (enrichment-scheduler feature)
**Entry Points:** `backend/main.py`, `backend/models.py`, `backend/schemas.py`

## High-Level Architecture

UKIP backend is a FastAPI application with domain-driven architecture, organized around entity management, enrichment, analytics, and knowledge synthesis. The system emphasizes safety through contracts (enums, TypedDicts), isolation (domain scoping, org isolation), and read-model factories (entity_base_q).

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│                     (backend/main.py)                        │
├─────────────────────────────────────────────────────────────┤
│                        12 Domain Routers                     │
├──────┬──────┬──────┬────────┬────────┬────────┬─────┬──────┤
│ auth │ingest│entity│enrichm-│harmon- │disamb- │rules│export│
│ users│      │      │ ation  │ization │ uation │     │      │
├──────┼──────┼──────┼────────┼────────┼────────┼─────┼──────┤
│ stores│integr-│domain│analyt-│ authority│ RAG │webhooks│
│       │ation │      │ tics  │          │     │        │
├─────────────────────────────────────────────────────────────┤
│                        Core Services                         │
│  entity_query (factory)  derived_status  entity_service     │
├─────────────────────────────────────────────────────────────┤
│                    Data Access Layer                         │
│         SQLAlchemy ORM + SQLite / DuckDB / ChromaDB        │
├─────────────────────────────────────────────────────────────┤
│                      Guards & Isolation                      │
│  domain_scope  tenant_access  auth  encryption              │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Modules

### main.py — Slim Orchestrator

**Location:** `backend/main.py` (~160 lines after Sprint 36 refactor)

**Purpose:** Application entry point, Lifespan management, Router registration

**Key responsibilities:**
```python
# 1. Pydantic settings
ALLOWED_ORIGINS = ["http://localhost:3004"]
DATABASE_URL = "sqlite:///./sql_app.db"
JWT_SECRET_KEY = env("JWT_SECRET_KEY")

# 2. FastAPI app with CORS
app = FastAPI(title="UKIP")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, ...)

# 3. Lifespan startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    _migrate_legacy_enrichment_status()  # Idempotent
    _bootstrap_super_admin()
    asyncio.create_task(enrichment_worker())
    yield
    # Shutdown
    pass

# 4. Register 12 routers
app.include_router(router_auth, prefix="/api")
app.include_router(router_ingest, prefix="/api")
# ...
```

**Anti-pattern avoided:** No business logic in main.py. All routing delegated to specific routers.

---

### models.py — SQLAlchemy ORM Models

**Location:** `backend/models.py`

**Key models:**

| Model | Purpose | Key Columns |
|-------|---------|------------|
| `RawEntity` | Source entities | id, source, domain, enrichment_status, validation_status, attributes_json, org_id |
| `User` | Auth principal | username, password_hash, role, is_active, org_id |
| `StoreConnection` | Data source credentials | store_type, config_json, credentials_encrypted, org_id |
| `AIIntegration` | LLM/API integration | service_name, api_key_encrypted, status, org_id |
| `NormalizationRule` | Harmonization rules | pattern, replacement, domain, status, org_id |
| `EntityRelationship` | Entity graph | source_id, target_id, relationship_type |
| `CatalogPortal` | User-facing view | title, domain_id, visibility, filters, org_id |
| `AuthorityRecord` | Authority resolution | field_name, original_value, authority_source, status, org_id |

**Indexing strategy:**
- Frequently filtered columns: `status`, `enrichment_status`, `validation_status`, `source`, `domain`, `org_id`
- All indexed for O(log n) query performance

---

### schemas.py — Pydantic Models & Contracts

**Location:** `backend/schemas.py`

**Three contract types:**

1. **Enums** (source of truth for categorical values)
   - `EnrichmentStatus` — none, pending, processing, completed, failed
   - `ValidationStatus` — pending, valid, invalid
   - `UserRole` — super_admin, admin, editor, viewer

2. **TypedDicts** (documentation + IDE assist)
   - `EntityAttributesDict` — 11 documented keys in enrichment output

3. **Pydantic Models** (API serialization)
   - `Entity`, `EntityCreate`, `EntityUpdate`
   - `User`, `UserCreate`, `UserResponse`
   - `AuthorityRecord`, `AuthorityRecandidateResponse`
   - `CatalogPortal`, `CatalogPortalCreate`

**Key principle:** Schemas are the contract between API and frontend. Changes here can break clients.

---

### database.py — Connection & Session Management

**Location:** `backend/database.py`

```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Async safety:** FastAPI dependency injection handles session per-request.

---

### auth.py — JWT Authentication & RBAC

**Location:** `backend/auth.py`

**Exports:**
- `authenticate_user(db, username, password)` → User | None
- `create_access_token(subject, role, expires_delta=None)` → str
- `get_current_user(token, db)` → User
- `require_role(*allowed_roles)` → Depends factory

**Flow:**
```
1. Login: POST /auth/token (OAuth2 form)
   → authenticate_user(username, password)
   → create_access_token(user_id, user.role)
   → Return JWT

2. Protected request: GET /entities?...
   → FastAPI extracts Bearer token
   → get_current_user(token, db) validates
   → Adds current_user to request context

3. Role check: @app.get("/admin")
   → get_current_user (any auth)
   OR
   → Depends(require_role("super_admin", "admin"))
```

**Features:**
- Account lockout after 5 failed attempts (15 min cooldown)
- Password change endpoint: `POST /users/me/password`
- Startup bootstrap: Creates super_admin from env vars

---

### domain_scope.py — Domain Isolation & Filtering

**Location:** `backend/domain_scope.py`

**Exports:**
- `parse_scope(scope_str: str) -> str` — Normalize scope input
- `resolve_domain_filter(scope: str, model: ORM) -> BinaryExpression | None` — Generate filter

**Scope values:**
- `"all"` — All domains (no filter)
- `"domain:science"` — Specific domain (filter: model.domain == "science")
- `"legacy_default"` — Legacy domain ID

**Example:**
```python
from backend.domain_scope import parse_scope, resolve_domain_filter

scope = parse_scope("domain:science")  # → "domain:science"
filt = resolve_domain_filter(scope, RawEntity)  # → RawEntity.domain == "science"
entities = db.query(RawEntity).filter(filt).all()
```

---

### tenant_access.py — Multi-Tenant Isolation

**Location:** `backend/tenant_access.py`

**Exports:**
- `scope_query_to_org(q: Query, model: ORM, org_id: int) -> Query` — Add org filter
- `resolve_request_org_id(db, current_user) -> int` — Extract org from user

**Usage:**
```python
org_id = resolve_request_org_id(db, current_user)
q = db.query(RawEntity).filter(...)
q = scope_query_to_org(q, RawEntity, org_id)
# Result: RawEntity.org_id == org_id added
```

---

### encryption.py — Credential Protection

**Location:** `backend/encryption.py`

**Exports:**
- `encrypt_credential(plain: str) -> str` — Fernet encryption
- `decrypt_credential(encrypted: str) -> str` — Fernet decryption

**When used:**
- StoreConnection.config_json — API keys, DB passwords
- AIIntegration.api_key — LLM API keys

**Key rotation:** ENCRYPTION_KEY env var (no built-in rotation, manual required).

---

## 12 Domain Routers

All routers follow the same pattern:
1. Import models, schemas, database, auth
2. Create APIRouter with tags
3. Define endpoints with appropriate Depends()
4. Call business logic (services or direct DB queries)
5. Return typed responses

### Router: auth_users

**Location:** `backend/routers/auth_users.py`

**Endpoints:**
- `POST /auth/token` — Login (OAuth2 form)
- `GET /users/me` — Current user profile
- `POST /users` — Create user (super_admin+)
- `GET /users` — List users (super_admin+)
- `PUT /users/{id}` — Update user (super_admin+)
- `DELETE /users/{id}` — Delete user (super_admin+)
- `POST /users/me/password` — Change password

---

### Router: ingest

**Location:** `backend/routers/ingest.py`

**Endpoints:**
- `POST /upload` — Upload CSV/Excel (editor+, 20 MB limit)
- `GET /enrich/stats` — Enrichment statistics (editor+)
- `POST /enrich/row` — Enrich single row (editor+)
- `POST /enrich/bulk` — Enrich multiple rows (editor+)
- `POST /enrich/montecarlo/{id}` — Monte Carlo sampling (editor+)

---

### Router: entities

**Location:** `backend/routers/entities.py`

**Endpoints:**
- `GET /entities` — List with filters, pagination, domain scope (viewer+)
- `GET /entities/grouped` — Grouped by status (viewer+)
- `PUT /entities/{id}` — Update single entity (editor+)
- `DELETE /entities/{id}` — Delete single entity (editor+)
- `DELETE /entities/all` — Purge with optional rule cleanup (admin+)

**Uses:** `entity_base_q` from entity_query service

---

### Router: analytics

**Location:** `backend/routers/analytics.py`

**Endpoints:**
- `GET /dashboard/summary` — Executive summary KPIs (viewer+)
- `GET /stats` — Detailed statistics (viewer+)
- `GET /concepts` — Top concepts (viewer+)
- `GET /concepts/{concept}` — Concept detail (viewer+)
- `GET /analyzers/topics/{domain}` — Topic modeling (viewer+)
- `GET /analyzers/cooccurrence/{domain}` — Concept pairs (viewer+)
- `GET /analyzers/clusters/{domain}` — Topic clusters (viewer+)
- `GET /analyzers/correlation/{domain}` — Field correlation (viewer+)

**Uses:** `entity_base_q` for all entity aggregations

---

### Router: disambiguation

**Location:** `backend/routers/disambiguation.py`

**Endpoints:**
- `GET /disambiguate/{field}` — Group similar values (viewer+)
- `POST /disambiguate/ai-resolve` — AI resolution (editor+)
- `POST /disambiguate/confirm` — Confirm resolution (editor+)
- `POST /disambiguate/reject` — Reject resolution (editor+)

**Uses:** `entity_base_q` for field grouping

---

### Router: harmonization

**Location:** `backend/routers/harmonization.py`

**Endpoints:**
- `POST /harmonization/apply` — Apply rule to entities (editor+)
- `POST /harmonization/apply-all` — Batch apply (editor+)
- `POST /harmonization/undo` — Undo application (editor+)
- `POST /harmonization/redo` — Redo application (editor+)

---

### Router: authority

**Location:** `backend/routers/authority.py`

**Endpoints:**
- `POST /authority/resolve` — Resolve with authority sources (editor+)
- `GET /authority/records` — List resolved records (viewer+)
- `POST /authority/{id}/confirm` — Confirm resolution (editor+)
- `POST /authority/{id}/reject` — Reject resolution (editor+)
- `DELETE /authority/{id}` — Delete record (editor+)
- `GET /authority/metrics` — Resolution metrics (viewer+)
- `GET /authority/{field}` — Lookup field values (viewer+)

---

### Router: rules

**Location:** `backend/routers/rules.py`

**Endpoints:**
- `POST /rules/bulk` — Create normalization rules (editor+)
- `PUT /rules/{id}` — Update rule (editor+)
- `DELETE /rules/{id}` — Delete rule (editor+)
- `GET /rules` — List with pagination (viewer+)
- `POST /rules/apply` — Apply rule to entities (editor+)

---

### Router: stores

**Location:** `backend/routers/stores.py`

**Endpoints:**
- `POST /stores` — Create store connection (admin+)
- `GET /stores` — List with pagination (admin+)
- `PUT /stores/{id}` — Update store (admin+)
- `DELETE /stores/{id}` — Delete store (admin+)
- `POST /stores/{id}/test` — Test connection (admin+)
- `POST /stores/{id}/pull` — Import data (admin+)

**Security:** Credentials encrypted at rest, decrypted on use only.

---

### Router: ai_rag

**Location:** `backend/routers/ai_rag.py`

**Endpoints:**
- `POST /ai-integrations` — Create LLM integration (admin+)
- `GET /ai-integrations` — List (admin+)
- `PUT /ai-integrations/{id}` — Update (admin+)
- `DELETE /ai-integrations/{id}` — Delete (admin+)
- `POST /rag/index` — Index entities into ChromaDB (editor+)
- `POST /rag/query` — Semantic search (viewer+)
- `GET /rag/stats` — Index statistics (viewer+)

---

### Router: derived_status

**Location:** `backend/routers/derived_status.py`

**Endpoints:**
- `GET /derived-status/{domain}` — Bundle of 6 resources (viewer+)

**Uses:** `DerivedStatusService.compute_all()`

---

### Router: reports

**Location:** `backend/routers/reports.py`

**Endpoints:**
- `GET /export` — HTML export (viewer+)
- `POST /exports/pdf` — PDF export (viewer+)
- `POST /exports/excel` — Excel export (viewer+)

---

## Core Services

### entity_query — Read-Model Factory

**Location:** `backend/services/entity_query.py`

**Purpose:** Centralised, safe RawEntity query factory with three mandatory guards.

**Exports:**
- `entity_base_q(db, scope, org_id)` → Query with all guards
- `count_total(db, scope, org_id)` → int
- `count_by_status(db, scope, status, org_id)` → int
- `count_enriched(db, scope, org_id)` → int

See [CODEMAPS: Entity Query](entity_query.md) for details.

---

### derived_status_service — Status Computation

**Location:** `backend/services/derived_status_service.py`

**Purpose:** Read-only status of 6 derived resources without triggering builds.

**Exports:**
- `DerivedStatusService.compute(resource, scope, db)` → dict
- `DerivedStatusService.compute_all(scope, db)` → dict
- `invalidate_derived_status_cache(domain_id)` → None

See [CODEMAPS: Derived Status](derived_status.md) for details.

---

### entity_service — Entity CRUD

**Location:** `backend/services/entity_service.py`

**Purpose:** Business logic for entity create, read, update, delete operations.

**Key methods:**
- `create_entity(db, entity_data, org_id)`
- `get_entity(db, entity_id, org_id)`
- `update_entity(db, entity_id, updates, org_id)`
- `delete_entity(db, entity_id, org_id)`

---

### enrichment_worker — Background Processing

**Location:** `backend/enrichment_worker.py`

**Purpose:** Async worker that processes enrichment_status=pending → completed.

**Process:**
1. Claim a pending entity (UPDATE WHERE status='pending')
2. Fetch from authority (WoS, OpenAlex, VIAF, etc.)
3. Write enrichment data to attributes_json
4. Update enrichment_status=completed
5. Call `invalidate_derived_status_cache(domain_id)`

---

### enrichment_scheduler — Scheduled Re-queuing Service

**Location:** `backend/services/enrichment_scheduler.py`

**Purpose:** Background service that detects stale domains and re-queues eligible entities.

**Model:** `DomainEnrichmentPolicy` per domain stores:
- `enabled` — whether scheduling is active
- `min_enrichment_pct` — target enrichment threshold (default: 80%)
- `max_budget_per_run` — max entities to requeue per cycle (default: 100)
- `staleness_threshold_days` — days since last run to trigger (default: 30)

**Audit log:** `EnrichmentSchedulerRun` records each scheduler invocation:
- `domain_id`, `triggered_at`, `queued_count`, `status` (started/completed/failed)

**Process (60-second loop):**
1. For each enabled domain policy:
   - Check if enrichment_pct < min_enrichment_pct AND age > staleness_threshold_days
   - If stale: requeue up to `max_budget_per_run` entities (status='none' or 'failed' → 'pending')
   - Record run attempt in EnrichmentSchedulerRun

**Singleton pattern:** Module-level `scheduler` instance created in main.py lifespan

---

### enrichment_schedule Router

**Location:** `backend/routers/enrichment_schedule.py`

**Endpoints:**
- `GET /enrichment/schedule` — Global scheduler state (last/next run, running status)
- `GET /enrichment/schedule/{domain_id}` — Per-domain staleness report (viewer+)
- `GET /enrichment/schedule/{domain_id}/runs` — Run history with pagination (viewer+)
- `POST /enrichment/schedule/{domain_id}/trigger` — Manual trigger (admin+)
- `PUT /enrichment/schedule/{domain_id}/policy` — Upsert/update policy (admin+, 201 on create)

**Auth:** All endpoints require `get_current_user`; write ops require `admin+`

---

## Data Flow Example: Upload & Enrichment

```
User UI: Click "Upload" with CSV
         ↓
POST /upload (editor+, 20 MB limit)
  ├─ ingest router
  ├─ Parse CSV
  ├─ Create RawEntity rows (source='user')
  ├─ Set enrichment_status=none
  └─ Return {batch_id, count}

User UI: View "Enrich" dashboard
         ↓
GET /enrich/stats (editor+)
  ├─ ingest router
  ├─ count = count_total(..., org_id)
  ├─ pending = count_by_status(..., EnrichmentStatus.pending, org_id)
  ├─ completed = count_enriched(..., org_id)
  └─ Return {total, pending, completed, ...}

User UI: Click "Start Enrichment"
         ↓
POST /enrich/bulk (editor+)
  ├─ ingest router
  ├─ entity_base_q(db, domain, org_id)
  │  .filter(status=none)
  │  .update({status: pending})
  └─ Return {queued: N}

Background: enrichment_worker task
  ├─ Loop: entity_base_q(db, "all", org_id=None) [admin context]
  │  .filter(status=pending)
  │  .limit(1)
  ├─ Claim entity (UPDATE WHERE status='pending' AND id=X)
  ├─ Set status=processing
  ├─ Fetch from authority (OpenAlex, WoS, etc.)
  ├─ Build attributes_json with 11 keys
  ├─ Set status=completed
  ├─ Call invalidate_derived_status_cache(domain_id)
  └─ Commit

User UI: GET /derived-status/domain:science
         ├─ Router checks cache (hit/miss)
         ├─ If miss: DerivedStatusService.compute_all(...)
         │  └─ _compute_enrichment(...) counts completed
         ├─ Cache for 30 sec
         └─ Return {enrichment: {status: ready, ...}, ...}
```

---

## Related Documentation

- [CODEMAPS: Schemas](schemas.md) — Enums and contracts
- [CODEMAPS: Entity Query](entity_query.md) — Safe RawEntity queries
- [CODEMAPS: Derived Status](derived_status.md) — Resource status computation
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — Full system design
