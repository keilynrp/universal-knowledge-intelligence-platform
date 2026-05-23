# Data Schemas & Contracts Codemap

**Last Updated:** 2026-05-22 (scientific affiliation normalization)
**Entry Points:** `backend/schemas.py`, `backend/models.py`

## Overview

The schemas module defines canonical enums, TypedDicts, and Pydantic models that form the single source of truth for all data structures across UKIP. This ensures consistency in how enrichment status, validation states, and entity attributes are represented.

## Key Contracts

### Scientific Enrichment Affiliation Contract

**Location:** `backend/schemas_enrichment.py`

`EnrichedRecord` now supports both legacy text affiliations and structured scientific affiliation metadata:

```python
class CanonicalAffiliation(BaseModel):
    name: str
    ror: str | None = None
    openalex_id: str | None = None
    country_code: str | None = None
    type: str | None = None
    lineage: list[str] = []

class AuthorAffiliation(BaseModel):
    author_name: str
    author_orcid: str | None = None
    author_openalex_id: str | None = None
    author_position: str | None = None
    author_order: int | None = None
    institutions: list[CanonicalAffiliation]
```

**Persistence:** `backend/enrichment_worker.py` writes `canonical_affiliations` and `author_affiliations` into `RawEntity.attributes_json` when an enrichment provider supplies them. It also keeps `affiliation` and `affiliations` for backward compatibility and geographic fallback.

**OpenAlex mapping:** `backend/adapters/enrichment/openalex.py` maps `authorships[].author` and `authorships[].institutions[]` into these structures, deduplicating canonical institutions by ROR, OpenAlex institution ID, then normalized name/country.

**Authority handoff:** `backend/services/scientific_affiliations.py` exposes `normalize_ror_id()` and `extract_institution_authority_candidates()` so institution reconciliation can consume persisted structured metadata without reparsing raw OpenAlex JSON.

**Analytics:** `backend/analyzers/geographic.py` prefers `canonical_affiliations[].country_code` before legacy affiliation text extraction.

### EnrichmentStatus Enum

**Location:** `backend/schemas.py` (lines 14–31)

```python
class EnrichmentStatus(str, Enum):
    """Canonical values for enrichment_status column."""
    none       = "none"        # Entity never queued for enrichment
    pending    = "pending"     # Queued, waiting for worker pickup
    processing = "processing"  # Worker actively enriching
    completed  = "completed"   # Enrichment finished successfully
    failed     = "failed"      # Enrichment finished with error
```

**Usage:**
- Written by enrichment workers in `backend/enrichment_worker.py`
- Queried by `backend/services/entity_query.py` and `derived_status_service.py`
- Displayed in frontend filters (`EnrichmentStatusFilter`, `/entities`)

**Migration:** Startup code in `backend/main.py` converts legacy "done"/"enriched" → "completed" (idempotent).

---

### ValidationStatus Enum

**Location:** `backend/schemas.py` (lines 34–38)

```python
class ValidationStatus(str, Enum):
    """Canonical values for validation_status column."""
    pending = "pending"  # Not yet validated
    valid   = "valid"    # Passed validation rules
    invalid = "invalid"  # Failed validation
```

**Usage:**
- Set by validation rules engine in `backend/routers/rules.py`
- Queried by `/entities`, `/entities/grouped` endpoints
- Displayed in frontend with color-coded badges

---

### EntityAttributesDict TypedDict

**Location:** `backend/schemas.py` (lines 45–65)

```python
class EntityAttributesDict(TypedDict, total=False):
    """Documented top-level keys in attributes_json (JSON Text column)."""
    enrichment_authors: list[str]
    enrichment_author_orcids: list[str | None]
    enrichment_affiliations: list[str]
    enrichment_funding: list[str]
    enrichment_mesh_terms: list[str]
    enrichment_tldr: str | None
    enrichment_influential_citation_count: int | None
    enrichment_references_count: int | None
    enrichment_license: str | None
    enrichment_venue: str | None
    enrichment_failure: str

KNOWN_ATTRIBUTE_KEYS: frozenset = frozenset(
    EntityAttributesDict.__annotations__.keys()
)
```

**Purpose:**
- **Documentation** — IDE autocompletion when accessing attributes_json
- **Validation** — Test suite verifies no undocumented keys in attributes_json
- **Contract** — Workers must only write these 11 keys; rejects unknown keys

**Where attributes_json is populated:**
- `backend/enrichment_worker.py` — Writes enrichment data as JSON
- `backend/services/derived_status_service.py` — Reads to compute status
- Frontend analytics — Parses for UI displays

**Important:** This is a TypedDict (documentation + IDE-assist only). Runtime enforcement happens via test assertions, not type checking.

---

## Database Models

**Location:** `backend/models.py`

### RawEntity Model

Key columns relevant to metadata contracts:

| Column | Type | Enum/Constraint | Constraint |
|--------|------|-----------------|-----------|
| `id` | Integer | | Primary key |
| `enrichment_status` | String | EnrichmentStatus | Not null, indexed |
| `validation_status` | String | ValidationStatus | Nullable |
| `attributes_json` | Text | EntityAttributesDict | Stores 11-key JSON |
| `source` | String | user\|demo\|adapter\|graph_materializer | Not null, indexed |
| `org_id` | Integer | | FK to org, multi-tenant isolation |
| `domain` | String | | Domain scoping |
| `created_at` | DateTime | | Indexed |
| `enrichment_doi` | String | | Enrichment output |
| `enrichment_concepts` | String | | Comma-separated concept list |
| `quality_score` | Float | | 0.0–1.0 |

---

## Core Pydantic Models

### EntityBase & Entity

```python
class EntityBase(BaseModel):
    primary_label: Optional[str] = None
    secondary_label: Optional[str] = None
    canonical_id: Optional[str] = None
    entity_type: Optional[str] = None
    domain: Optional[str] = None
    validation_status: Optional[str] = None
    enrichment_doi: Optional[str] = None
    enrichment_citation_count: Optional[int] = 0
    enrichment_concepts: Optional[str] = None
    enrichment_source: Optional[str] = None
    enrichment_status: Optional[str] = EnrichmentStatus.none  # Default
    quality_score: Optional[float] = None

class Entity(EntityBase):
    id: int
    import_batch_id: Optional[int] = None
    attributes_json: Optional[str] = None
    normalized_json: Optional[str] = None
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
```

**Usage:**
- API request/response serialization
- ORM mapping via `from_attributes=True`
- Frontend type definitions

---

## Catalog Portal Facets

**Location:** `backend/schemas.py` (lines 96–143)

Catalog portals expose four facets by default:

```python
CATALOG_PORTAL_FACETS_DEFAULT = [
    "entity_type",
    "validation_status",
    "enrichment_status",    # ← Uses EnrichmentStatus enum
    "source",
]
```

**Filtering:** Users can filter by:
- `ft_entity_type`
- `ft_validation_status` — Valid values: pending, valid, invalid
- `ft_enrichment_status` — Valid values: none, pending, processing, completed, failed
- `ft_source` — Valid values: user, demo, adapter, graph_materializer

---

## Startup Migration: Legacy Status Conversion

**Location:** `backend/main.py` (lifespan startup)

Idempotent migration converts legacy enrichment_status values:

```python
def _migrate_legacy_enrichment_status():
    """One-time conversion: 'done'/'enriched' → 'completed'."""
    with SessionLocal() as db:
        # Only touch rows with legacy values
        db.query(RawEntity).filter(
            RawEntity.enrichment_status.in_(["done", "enriched"])
        ).update({"enrichment_status": EnrichmentStatus.completed})
        db.commit()
```

**Idempotency:** After first run, query matches zero rows, no-op on subsequent starts.

---

## Testing & Validation

### test_entity_metadata_contract.py (21 tests)

Tests validate:
1. EnrichmentStatus enum values are canonical
2. ValidationStatus enum values are correct
3. EntityAttributesDict keys match KNOWN_ATTRIBUTE_KEYS
4. Legacy migration converts "done"/"enriched" → "completed"
5. attributes_json from workers contains only known keys
6. Pydantic models serialize/deserialize correctly
7. Database migrations applied without errors

**Key fixtures:**
- `db_session` — Direct DB access for assertions
- `enrichment_worker_output` — Mock enrichment output

---

## Dependency Map

```
backend/schemas.py (defines EnrichmentStatus, ValidationStatus, EntityAttributesDict)
    ↓
    Used by:
    ├── backend/models.py (RawEntity columns)
    ├── backend/enrichment_worker.py (writes to attributes_json)
    ├── backend/services/entity_query.py (queries by status)
    ├── backend/services/derived_status_service.py (counts by status)
    ├── backend/routers/entities.py (filters, displays)
    ├── backend/routers/analytics.py (status aggregation)
    └── frontend/app/components/EntityFilter.tsx (dropdown options)
```

---

## Anti-Patterns & What NOT to Do

❌ **Do NOT** hardcode status strings in routers:
```python
# WRONG
if row.enrichment_status == "completed":
```

✅ **DO** use the enum:
```python
# RIGHT
if row.enrichment_status == EnrichmentStatus.completed:
```

---

❌ **Do NOT** write arbitrary keys to attributes_json:
```python
# WRONG
attributes_json["custom_field"] = "value"
```

✅ **DO** only write documented keys; extend TypedDict if needed:
```python
# RIGHT
attributes_json["enrichment_authors"] = [...]
```

---

❌ **Do NOT** bypass domain/org filtering in queries:
```python
# WRONG
db.query(RawEntity).filter(RawEntity.enrichment_status == status).all()
```

✅ **DO** use entity_base_q() from entity_query service:
```python
# RIGHT
from backend.services.entity_query import entity_base_q
entity_base_q(db, domain_id, org_id).filter(...).all()
```

---

## Quick Reference

| Enum/Type | Purpose | Values/Keys | Nullable |
|-----------|---------|------------|----------|
| `EnrichmentStatus` | Enrichment lifecycle | 5 states | No (default: none) |
| `ValidationStatus` | Validation result | 3 states | Yes |
| `EntityAttributesDict` | enrichment outputs | 11 keys | N/A (documentation) |
| `KNOWN_ATTRIBUTE_KEYS` | Validation set | Frozenset of 11 | N/A (constant) |

## Enrichment Scheduler Schemas (NEW)

**Location:** `backend/schemas.py` (new classes)

### DomainEnrichmentPolicySchema

```python
class DomainEnrichmentPolicySchema(BaseModel):
    """Per-domain enrichment scheduling configuration."""
    domain_id: str
    enabled: bool
    min_enrichment_pct: float     # Default: 80.0
    max_budget_per_run: int       # Default: 100
    staleness_threshold_days: int  # Default: 30
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DomainEnrichmentPolicyUpdate(BaseModel):
    """Update payload for policy endpoints."""
    enabled: Optional[bool] = None
    min_enrichment_pct: Optional[float] = Field(None, ge=0, le=100)
    max_budget_per_run: Optional[int] = Field(None, ge=1, le=10000)
    staleness_threshold_days: Optional[int] = Field(None, ge=1, le=365)
```

**Database model:** `backend/models.DomainEnrichmentPolicy` (table created via migration)

---

### EnrichmentSchedulerRunSchema

```python
class EnrichmentSchedulerRunSchema(BaseModel):
    """Audit log entry for each scheduler invocation."""
    id: int
    domain_id: str
    triggered_at: datetime
    queued_count: int
    status: str  # "started", "completed", "failed"
    error_message: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
```

**Database model:** `backend/models.EnrichmentSchedulerRun` (table created via migration)

---

### DomainStalenessReport

```python
class DomainStalenessReport(BaseModel):
    """Staleness assessment for a single domain."""
    domain_id: str
    total_entities: int
    enriched_entities: int
    stale_entities: int
    current_enrichment_pct: float
    is_stale: bool
    policy: DomainEnrichmentPolicySchema
```

---

### SchedulerStateResponse

```python
class SchedulerStateResponse(BaseModel):
    """Global enrichment scheduler state."""
    running: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    interval_seconds: int
    enabled_domains: int
```

---

## Related Documentation

- [CODEMAPS: Entity Query Read-Model](entity_query.md) — How to safely query RawEntity
- [CODEMAPS: Derived Status Service](derived_status.md) — How to compute resource status
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — Full system architecture
