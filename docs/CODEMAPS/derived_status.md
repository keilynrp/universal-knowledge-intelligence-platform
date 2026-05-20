# Derived Data Status Service Codemap

**Last Updated:** 2026-05-20  
**Entry Points:** `backend/services/derived_status_service.py`, `backend/routers/derived_status.py`

## Overview

The Derived Data Status Service tracks the build/freshness status of six derived data resources. It is a **read-only** service that computes status from existing database state without modifying data or triggering pipelines.

## Six Tracked Resources

| Resource | Purpose | Count Metric | Status Logic |
|----------|---------|--------------|--------------|
| **enrichment** | Source data enriched with external metadata | RawEntity with `enrichment_status=completed` | Ready if all enriched; Missing if none; Stale if partial |
| **graph** | Entity relationship graph | RawEntity IDs that appear in EntityRelationship | Ready if ≥source count; Stale if partial |
| **semantic_keyword_signals** | Computed concept signals | RawEntity with `enrichment_concepts` non-empty | Ready if ≥source count; Stale if partial |
| **rag_index** | Vectorized ChromaDB index | Total indexed docs in ChromaDB | Ready if ≥source count; Stale if partial; Unknown if ChromaDB unreachable |
| **executive_dashboard_snapshot** | Analytics cache warmth | Dashboard cache entries | Ready if cache warm; Stale if cache cold |
| **report_readiness** | Ability to generate reports | RawEntity with `enrichment_status=completed` | Ready if ≥50% enriched; Missing if 0 enriched |

---

## Service Architecture

### Status Constants

**Location:** `backend/services/derived_status_service.py` (lines 26–47)

```python
STATUS_MISSING     = "missing"      # Resource does not exist
STATUS_PENDING     = "pending"      # Queued but not started
STATUS_PROCESSING  = "processing"   # Currently being built
STATUS_READY       = "ready"        # Complete and usable
STATUS_STALE       = "stale"        # Partial (outdated)
STATUS_FAILED      = "failed"       # Build terminated with error
STATUS_UNKNOWN     = "unknown"      # Unable to determine (transient error)

CANONICAL_STATUSES = frozenset({
    STATUS_MISSING, STATUS_PENDING, STATUS_PROCESSING,
    STATUS_READY, STATUS_STALE, STATUS_FAILED, STATUS_UNKNOWN,
})
```

### TTL Cache

**Location:** `backend/services/derived_status_service.py` (lines 63–95)

Thread-safe in-memory cache with 30-second TTL and domain+org scoping:

```python
class _StatusCache:
    def __init__(self, ttl_seconds: int = 30):
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        # Evict if expired
        
    def set(self, key: str, value: Any) -> None:
        # Store with timestamp
        
    def invalidate(self, domain_id: str) -> None:
        # Evict all entries for a domain
```

**Cache Key Pattern:** `"{domain_id}:{org_id}"`

**Invalidation:** Call `invalidate_derived_status_cache(domain_id)` from enrichment workers or materializers after a build completes.

---

## Per-Resource Computation

### _compute_enrichment(scope, db)

**Lines 144–163**

```
Count: total source entities vs. enrichment_status=completed
Logic:
  - Missing:  source_count=0
  - Missing:  source_count>0, derived_count=0
  - Stale:    0 < derived_count < source_count
  - Ready:    derived_count=source_count
```

### _compute_graph(scope, db)

**Lines 166–194**

```
Count: distinct RawEntity IDs in EntityRelationship.source_id
Join: EntityRelationship → RawEntity (for domain scoping)
Logic:
  - Missing:  source_count=0 OR derived_count=0
  - Stale:    0 < derived_count < source_count
  - Ready:    derived_count≥source_count
```

### _compute_semantic_keyword_signals(scope, db)

**Lines 197–217**

```
Count: RawEntity with enrichment_concepts non-null and non-empty
Logic:
  - Missing:  source_count=0 OR derived_count=0
  - Stale:    0 < derived_count < source_count
  - Ready:    derived_count≥source_count
```

### _compute_rag_index(scope, db)

**Lines 220–245**

```
Count: VectorStoreService.get_stats()["total_indexed"] from ChromaDB
Fallback: Catches ChromaDB connection errors → STATUS_UNKNOWN
Logic:
  - Missing:  source_count=0 OR derived_count=0
  - Stale:    0 < derived_count < source_count
  - Ready:    derived_count≥source_count
  - Unknown:  ChromaDB unreachable (error logged, recoverable)
```

### _compute_executive_dashboard_snapshot(scope, db)

**Lines 248–285**

```
Check: Analytics dashboard cache warmth
Pattern: "dashboard_{domain_id}" entries in _dashboard_cache
Cache TTL: 30 seconds (same as status cache)
Fallback: If cache inspection fails → STATUS_READY (optimistic)
Logic:
  - Missing:  source_count=0
  - Stale:    source_count>0 AND cache expired
  - Ready:    cache warm
```

### _compute_report_readiness(scope, db)

**Lines 288–314**

```
Count: RawEntity with enrichment_status=completed
Threshold: ≥50% enriched (pragmatic, not 100%)
Logic:
  - Missing:  source_count=0
  - Missing:  derived_count=0
  - Stale:    0 < derived_count < 50% * source_count
  - Ready:    derived_count≥50% * source_count
```

---

## Public API

### DerivedStatusService.compute()

```python
@staticmethod
def compute(resource: str, scope: str, db: Session) -> dict[str, Any]:
    """
    Compute status of a single resource.
    
    Args:
        resource: One of TRACKED_RESOURCES
        scope: Domain scope (e.g., "all", "domain:science")
        db: SQLAlchemy session
        
    Returns:
        {
            "status": str,              # One of CANONICAL_STATUSES
            "updated_at": str (ISO),    # Computation timestamp
            "source_count": int,        # Total source entities
            "derived_count": int,       # Derived entities
            "last_error": str | None,   # Error message if status=unknown
            "can_rebuild": bool,        # True if rebuild endpoint available
            "rebuild_endpoint": str,    # e.g., "/enrich/bulk"
        }
    """
```

### DerivedStatusService.compute_all()

```python
@staticmethod
def compute_all(scope: str, db: Session) -> dict[str, Any]:
    """
    Compute all six resources and return the bundle.
    
    Returns:
        {
            "domain_id": str,
            "computed_at": str (ISO),
            "resources": {
                "enrichment": {...},
                "graph": {...},
                "semantic_keyword_signals": {...},
                "rag_index": {...},
                "executive_dashboard_snapshot": {...},
                "report_readiness": {...},
            }
        }
    """
```

### invalidate_derived_status_cache()

```python
def invalidate_derived_status_cache(domain_id: str) -> None:
    """Evict cache entries for a domain. Call after builds complete."""
```

---

## Router Integration

**Location:** `backend/routers/derived_status.py`

### GET /derived-status/{domain_id}

```python
@router.get("/derived-status/{domain_id}")
def get_derived_status(
    domain_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict:
```

**Parameters:**
- `domain_id` — Any scope: "all", "domain:science", "legacy_default", etc.

**Behavior:**
1. Validates domain exists in registry (except "all")
2. Checks cache (key: `"{domain_id}:{org_id}"`)
3. If hit: return cached result
4. If miss: call `DerivedStatusService.compute_all(scope, db)`
5. Cache result for 30 seconds
6. Return bundle

**Responses:**
- `200 OK` — Full bundle with 6 resources
- `404 Not Found` — Domain not found in registry
- `500 Internal Server Error` — Computation failed

**Auth:** Requires `get_current_user` (any authenticated user)

---

## Frontend Integration

**Location:** `frontend/app/analytics/dashboard/DerivedStatusPanel.tsx` (conceptual)

Panel displays:
- Status badge per resource (ready=green, stale=yellow, missing=red, unknown=gray)
- Source count vs. derived count
- Last update timestamp
- "Rebuild" button for each resource (when `can_rebuild=true`)

---

## Data Flow

```
┌─────────────────────────────────────────┐
│ Enrichment Worker / Graph Materializer  │
│ (completes build)                       │
└────────────────┬────────────────────────┘
                 │
                 ├─→ Call invalidate_derived_status_cache(domain_id)
                 │
                 └─→ Cache entry deleted
                     (next /derived-status call will recompute)
                     
┌──────────────────────────────────────────┐
│ Frontend: GET /derived-status/{domain}   │
└────────────────┬─────────────────────────┘
                 │
          ┌──────▼──────┐
          │ Cache hit?  │
          └──────┬──────┘
             No  │  Yes
                 │    └─→ Return cached result
                 │
        ┌────────▼─────────────────┐
        │ DerivedStatusService     │
        │ .compute_all(scope, db)  │
        │                          │
        │ Calls 6 _compute_* fns   │
        │ Each uses entity_base_q  │
        └────────┬────────────────┘
                 │
        ┌────────▼────────────────────────┐
        │ Return bundle with 6 resources  │
        │ Cache for 30 seconds            │
        └────────┬───────────────────────┘
                 │
        ┌────────▼──────────────────┐
        │ Frontend renders panel    │
        │ Shows status + rebuild    │
        └───────────────────────────┘
```

---

## Scoping & Isolation

**Domain Scoping:** All computations use `entity_base_q(db, scope, org_id)` which:
1. Applies domain filter via `resolve_domain_filter`
2. Applies org isolation via `scope_query_to_org`
3. Excludes graph_materializer synthetic rows

**Org Isolation:** Cache key includes `org_id`, so each tenant sees independent status.

---

## Error Handling

| Scenario | Status | last_error | can_rebuild |
|----------|--------|-----------|-------------|
| ChromaDB unreachable | unknown | "ChromaDB unreachable: ..." | False |
| Dashboard cache inspection fails | ready | None | True (optimistic) |
| SQL query error | unknown | str(exc) | False |
| Normal computation | varies | None | depends on status |

**Logging:** Errors are logged at WARNING level; computation continues with best-effort values.

---

## Testing Strategy

Tests in `backend/tests/test_*` validate:
1. Status constants are canonical
2. Each _compute_* function returns correct status for given counts
3. Cache works (set, get, expire, invalidate)
4. Cache scoping by org_id
5. Router returns correct HTTP status codes
6. Domain existence validation
7. Error handling (ChromaDB down, SQL error, etc.)

**Key fixtures:**
- `db_session` — Test DB with sample data
- `auth_headers` — Super admin JWT
- `domain_scope` — Parsed scope values

---

## Related Documentation

- [CODEMAPS: Entity Query Read-Model](entity_query.md) — How `entity_base_q` is used
- [CODEMAPS: Schemas](schemas.md) — EnrichmentStatus enum
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — Full system architecture
- [docs/DELIVERY_OPERATING_SYSTEM.md](../DELIVERY_OPERATING_SYSTEM.md) — Build orchestration
