# Entity Query Read-Model Codemap

**Last Updated:** 2026-05-20  
**Entry Points:** `backend/services/entity_query.py`

## Overview

The Entity Query Read-Model service provides a safe, centralized factory for building RawEntity queries with three mandatory guards automatically applied:

1. **Exclude synthetic rows** — `source != 'graph_materializer'`
2. **Apply domain scoping** — Via `resolve_domain_filter` from domain_scope module
3. **Apply org isolation** — Via `scope_query_to_org` from tenant_access module

This prevents accidental data leaks or silent cross-tenant/cross-domain access.

## Problem It Solves

Before this service, RawEntity queries were scattered across multiple routers with inconsistent filtering:

```python
# OLD (WRONG) — routers.entities.py
db.query(RawEntity).filter(RawEntity.domain == domain_id).all()
# Misses: graph_materializer filter, org isolation

# OLD (WRONG) — routers.analytics.py
db.query(RawEntity).filter(...).offset(skip).limit(limit)
# Misses: domain scope, org isolation, graph_materializer filter

# NEW (RIGHT) — using entity_base_q
from backend.services.entity_query import entity_base_q
entity_base_q(db, domain_id, org_id).filter(...).all()
# All three guards applied automatically
```

---

## Core API

### entity_base_q()

**Location:** `backend/services/entity_query.py` (lines 44–77)

```python
def entity_base_q(
    db: Session,
    scope: str,
    org_id: Optional[int] = None,
) -> Query:
    """
    Return a SQLAlchemy Query for RawEntity with all three mandatory guards.
    
    Args:
        db:     Active SQLAlchemy session
        scope:  Domain scope string:
                - "all"              → All domains
                - "domain:science"   → Single domain
                - "legacy_default"   → Legacy domain ID
                Parsed internally via parse_scope()
        org_id: Org ID for multi-tenant isolation
                - Pass None to skip org scoping (admin/batch contexts only)
                - WARNING: Pass None only when certain — production
                           request handlers MUST pass org_id
    
    Returns:
        SQLAlchemy Query that can be further filtered, limited, ordered, executed
    
    Raises:
        Nothing directly; invalid scope returns empty-ish filter (see parse_scope)
    """
    parsed = parse_scope(scope)
    
    # Guard 1: Exclude graph_materializer synthetic rows
    q: Query = db.query(models.RawEntity).filter(
        models.RawEntity.source != _GRAPH_MATERIALIZER_SOURCE
    )
    
    # Guard 2: Apply domain scoping via resolve_domain_filter
    domain_filt = resolve_domain_filter(parsed, models.RawEntity)
    if domain_filt is not None:
        q = q.filter(domain_filt)
    
    # Guard 3: Apply org isolation if org_id provided
    if org_id is not None:
        q = scope_query_to_org(q, models.RawEntity, org_id)
    
    return q
```

### count_total()

**Location:** `backend/services/entity_query.py` (lines 80–86)

```python
def count_total(
    db: Session,
    scope: str,
    org_id: Optional[int] = None,
) -> int:
    """Count all non-derived entities in the scope."""
    return entity_base_q(db, scope, org_id).count()
```

### count_by_status()

**Location:** `backend/services/entity_query.py` (lines 89–100)

```python
def count_by_status(
    db: Session,
    scope: str,
    status: EnrichmentStatus,
    org_id: Optional[int] = None,
) -> int:
    """Count entities with the given EnrichmentStatus in scope."""
    return (
        entity_base_q(db, scope, org_id)
        .filter(models.RawEntity.enrichment_status == status)
        .count()
    )
```

### count_enriched()

**Location:** `backend/services/entity_query.py` (lines 103–109)

```python
def count_enriched(
    db: Session,
    scope: str,
    org_id: Optional[int] = None,
) -> int:
    """Convenience: count entities with enrichment_status=completed."""
    return count_by_status(db, scope, EnrichmentStatus.completed, org_id)
```

---

## The Three Guards Explained

### Guard 1: Exclude graph_materializer Source

**What it does:** Filters out synthetic rows created by the graph materializer.

```python
models.RawEntity.source != _GRAPH_MATERIALIZER_SOURCE  # "graph_materializer"
```

**Why it matters:**
- The graph materializer creates derived synthetic RawEntity rows to represent relationship nodes
- These rows have `source="graph_materializer"` as a marker
- User-facing queries should not include these; they inflate counts and confuse users
- Analytics, enrichment, and export only want real (user-uploaded or imported) entities

**Example:**
```python
# WITHOUT guard: 1000 user entities + 500 synthetic = 1500 total
# WITH guard: 1000 user entities only
```

### Guard 2: Domain Scoping via resolve_domain_filter()

**Location:** `backend/domain_scope.py`

```python
domain_filt = resolve_domain_filter(parsed, models.RawEntity)
if domain_filt is not None:
    q = q.filter(domain_filt)
```

**What it does:**
- Parses scope string ("domain:science", "legacy_default", "all")
- Returns a SQLAlchemy filter expression specific to RawEntity
- For "all" scope, returns None (no filter needed)

**Example:**
```python
# resolve_domain_filter("domain:science", RawEntity) 
#   → RawEntity.domain == "science"
# resolve_domain_filter("all", RawEntity)
#   → None (no filter, matches all)
```

**Prevents:** Cross-domain data leaks; ensures domain isolation.

### Guard 3: Org Isolation via scope_query_to_org()

**Location:** `backend/tenant_access.py`

```python
if org_id is not None:
    q = scope_query_to_org(q, models.RawEntity, org_id)
```

**What it does:**
- Adds row-level security filter based on org_id
- Typically adds `RawEntity.org_id == org_id`
- Multi-tenant isolation: Org A users never see Org B data

**Example:**
```python
# scope_query_to_org(q, RawEntity, org_id=5)
#   → Adds filter: RawEntity.org_id == 5
```

**Prevents:** Multi-tenant data leaks; ensures org isolation.

**Critical:** Production request handlers MUST pass `org_id`. Passing `None` is only safe in:
- Admin/batch utilities (explicit intent)
- Tests (controlled environment)
- Services that explicitly ignore org context

---

## Usage Patterns

### Pattern 1: Simple Count

```python
from backend.services.entity_query import count_total, count_enriched

total = count_total(db, "domain:science", org_id=user_org)
enriched = count_enriched(db, "domain:science", org_id=user_org)
pct = (enriched / total * 100) if total else 0
```

### Pattern 2: Filtered Query with Limit

```python
from backend.services.entity_query import entity_base_q

q = entity_base_q(db, domain_id, org_id)
results = (
    q
    .filter(models.RawEntity.quality_score > 0.8)
    .filter(models.RawEntity.validation_status == "valid")
    .order_by(models.RawEntity.created_at.desc())
    .limit(100)
    .all()
)
```

### Pattern 3: Aggregation (group_by, count)

```python
from sqlalchemy import func
from backend.services.entity_query import entity_base_q

grouped = (
    entity_base_q(db, domain_id, org_id)
    .group_by(models.RawEntity.validation_status)
    .with_entities(
        models.RawEntity.validation_status,
        func.count(models.RawEntity.id).label("count")
    )
    .all()
)
# Result: [(validation_status, count), ...]
```

### Pattern 4: Distinct with Order

```python
from backend.services.entity_query import entity_base_q

concepts = (
    entity_base_q(db, domain_id, org_id)
    .filter(models.RawEntity.enrichment_concepts.isnot(None))
    .with_entities(models.RawEntity.enrichment_concepts)
    .distinct()
    .limit(50)
    .all()
)
```

---

## Migrated Routers

The following routers have been refactored to use `entity_base_q`:

| Router | Functions | Commit |
|--------|-----------|--------|
| `backend/routers/entities.py` | `/entities`, `/entities/grouped`, enrich-stats | Sprint N |
| `backend/routers/analytics.py` | `/dashboard/summary`, `/stats`, concept clouds | Sprint N |
| `backend/routers/disambiguation.py` | Field-group queries, disambiguation counts | Sprint N |
| `backend/services/derived_status_service.py` | All 6 resource computations | Sprint N |
| `backend/routers/deps.py` | Helper functions for org/domain resolution | Sprint N |

**Remaining routers:** Search for old patterns (direct `db.query(RawEntity)` without guards) and migrate when refactoring those areas.

---

## How to Find Non-Compliant Queries

Search for patterns that bypass the factory:

```bash
# Find direct RawEntity queries (rough grep)
grep -r "db.query(models.RawEntity)" backend/routers/ | grep -v entity_base_q

# Find bare .filter(domain without using entity_base_q
grep -r "\.filter.*RawEntity\.domain" backend/ | grep -v entity_base_q
```

These should be migrated to use `entity_base_q` to ensure all three guards are applied.

---

## Testing Strategy

### test_entity_query.py (11 tests)

**Location:** `backend/tests/test_entity_query.py`

Tests validate:

1. **Guard 1 (graph_materializer exclusion)**
   - Create 5 real entities + 3 synthetic graph_materializer rows
   - `entity_base_q(...).count()` returns 5 (not 8)

2. **Guard 2 (domain scoping)**
   - Create entities in domains "science", "healthcare", "default"
   - `entity_base_q(db, "domain:science")` returns only science entities
   - `entity_base_q(db, "all")` returns all

3. **Guard 3 (org isolation)**
   - Create entities for org_id 1 and org_id 2
   - `entity_base_q(db, "all", org_id=1)` returns only org 1 entities
   - `entity_base_q(db, "all", org_id=2)` returns only org 2 entities
   - `entity_base_q(db, "all", org_id=None)` returns all (admin context)

4. **count_total()**
   - Verify count matches entity_base_q().count()

5. **count_by_status()**
   - Create mix of pending, processing, completed, failed statuses
   - count_by_status(..., EnrichmentStatus.completed) returns correct count

6. **count_enriched()**
   - count_enriched() == count_by_status(..., EnrichmentStatus.completed)

7. **Chaining filters**
   - entity_base_q().filter(quality > 0.8) works
   - Returns entities after all guards + filter

8. **Order and limit**
   - entity_base_q().order_by(...).limit(10) works

9. **Distinct queries**
   - entity_base_q().distinct() with certain columns works

10. **Empty scope handling**
    - entity_base_q(db, "domain:nonexistent") returns empty query

11. **Error handling**
    - entity_base_q with invalid scope parameter gracefully handles

---

## Import Guidance

**Always import from the service, never directly instantiate:**

```python
# RIGHT
from backend.services.entity_query import entity_base_q, count_enriched

# WRONG (bypass guards)
from backend.models import RawEntity
db.query(RawEntity)
```

---

## Performance Considerations

- **Index on source:** `RawEntity.source` is indexed (small cardinality)
- **Index on domain:** `RawEntity.domain` is indexed
- **Index on org_id:** `RawEntity.org_id` is indexed
- **Composite filtering:** All three guards are fast sequential filters

**Avoid N+1:**
```python
# WRONG: N+1 query
for entity in entity_base_q(...).all():
    # Lazy-load some relationship
    _ = entity.some_relationship

# RIGHT: Load relationships upfront
entity_base_q(...).options(joinedload(RawEntity.some_relationship)).all()
```

---

## Dependency Map

```
backend/services/entity_query.py (factory)
    ├─ Uses: backend/domain_scope.py (resolve_domain_filter)
    ├─ Uses: backend/tenant_access.py (scope_query_to_org)
    ├─ Uses: backend/schemas.py (EnrichmentStatus)
    └─ Uses: backend/models.py (RawEntity)

Consumed by:
    ├─ backend/routers/entities.py
    ├─ backend/routers/analytics.py
    ├─ backend/routers/disambiguation.py
    ├─ backend/services/derived_status_service.py
    ├─ backend/routers/deps.py
    └─ (more routers to migrate)
```

---

## Anti-Patterns & What NOT to Do

❌ **Do NOT** bypass the factory:
```python
# WRONG
db.query(RawEntity).filter(RawEntity.domain == domain_id).all()
# Missing: graph_materializer exclusion, org isolation
```

✅ **DO** use the factory:
```python
# RIGHT
from backend.services.entity_query import entity_base_q
entity_base_q(db, domain_id, org_id).all()
# All three guards applied
```

---

❌ **Do NOT** pass None for org_id in production request handlers:
```python
# WRONG (in a request handler)
count = entity_base_q(db, domain_id, org_id=None).count()
# Silent cross-tenant data leak
```

✅ **DO** resolve org_id from current_user:
```python
# RIGHT
from backend.routers.deps import resolve_request_org_id
org_id = resolve_request_org_id(db, current_user)
count = entity_base_q(db, domain_id, org_id).count()
```

---

❌ **Do NOT** forget to limit large queries:
```python
# WRONG (potential OOM)
all_entities = entity_base_q(db, "all", org_id).all()
```

✅ **DO** add explicit limit:
```python
# RIGHT
page = entity_base_q(db, "all", org_id).offset(skip).limit(100).all()
```

---

## Related Documentation

- [CODEMAPS: Schemas](schemas.md) — EnrichmentStatus enum
- [CODEMAPS: Derived Status Service](derived_status.md) — Consumes entity_base_q
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — Multi-tenancy & domain scoping
