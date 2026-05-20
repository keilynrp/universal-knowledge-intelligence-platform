# enrichment-status-enum Specification

## Purpose
TBD - created by archiving change entity-metadata-contract. Update Purpose after archive.
## Requirements
### Requirement: EnrichmentStatus canonical enum
The system SHALL define `EnrichmentStatus` as a Pydantic `str`-based enum in `backend/schemas.py` with exactly five values: `none`, `pending`, `processing`, `completed`, `failed`. No other values SHALL be written to the `enrichment_status` column by application code.

#### Scenario: Enum covers all lifecycle stages
- **WHEN** the enrichment pipeline transitions an entity through its lifecycle
- **THEN** each transition MUST use one of the five enum constants: `EnrichmentStatus.none`, `EnrichmentStatus.pending`, `EnrichmentStatus.processing`, `EnrichmentStatus.completed`, `EnrichmentStatus.failed`

#### Scenario: No bare string literals for status comparison
- **WHEN** any backend module compares or sets `enrichment_status`
- **THEN** it SHALL import and use `EnrichmentStatus` constants rather than bare string literals like `"completed"` or `"done"`

---

### Requirement: ValidationStatus canonical enum
The system SHALL define `ValidationStatus` as a Pydantic `str`-based enum in `backend/schemas.py` with three values: `pending`, `valid`, `invalid`.

#### Scenario: Enum used in EntityBase schema
- **WHEN** `EntityBase` is instantiated with a `validation_status` value
- **THEN** the value SHALL be one of the `ValidationStatus` enum members

---

### Requirement: Startup migration consolidates legacy status synonyms
The system SHALL execute an idempotent SQL UPDATE during FastAPI lifespan startup that sets `enrichment_status = 'completed'` for all rows where `enrichment_status IN ('done', 'enriched')`.

#### Scenario: Migration converts legacy rows
- **WHEN** the application starts and the database contains rows with `enrichment_status = 'done'` or `enrichment_status = 'enriched'`
- **THEN** those rows SHALL have `enrichment_status = 'completed'` after startup completes

#### Scenario: Migration is idempotent
- **WHEN** the application restarts after the migration has already run
- **THEN** the UPDATE affects zero rows and no error is raised

#### Scenario: No legacy values remain after migration
- **WHEN** the migration has completed
- **THEN** a query `SELECT COUNT(*) FROM raw_entities WHERE enrichment_status IN ('done','enriched')` SHALL return 0

---

### Requirement: derived_status_service uses enum constant
The system SHALL use `EnrichmentStatus.completed` (not a bare string list) when filtering enriched entities in `DerivedStatusService`.

#### Scenario: Enrichment resource status uses enum
- **WHEN** `DerivedStatusService.compute("enrichment", scope, db)` is called
- **THEN** the filter applied to count derived entities SHALL use `EnrichmentStatus.completed` value

---

### Requirement: Frontend uses canonical "completed" value
The frontend SHALL use only the string `"completed"` when filtering or displaying enrichment status — not `"done"` or `"enriched"`.

#### Scenario: Filter chip shows correct label
- **WHEN** a user filters entities by enrichment status `"completed"`
- **THEN** the API returns all entities where `enrichment_status = 'completed'` (legacy synonyms no longer exist in DB)

