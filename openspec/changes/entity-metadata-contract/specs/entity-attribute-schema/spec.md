## ADDED Requirements

### Requirement: EntityAttributesDict TypedDict documents known attributes_json keys
The system SHALL define an `EntityAttributesDict` `TypedDict` in `backend/schemas.py` that documents all known top-level keys written by enrichment workers into `attributes_json`. The TypedDict SHALL be documentation and IDE-assist only — not enforced at runtime.

#### Scenario: TypedDict lists all known enrichment-written keys
- **WHEN** a developer reads `EntityAttributesDict` in `backend/schemas.py`
- **THEN** they SHALL find typed annotations for all top-level keys that enrichment workers write:
  - `enrichment_authors: list[str]`
  - `enrichment_author_orcids: list[str | None]`
  - `enrichment_affiliations: list[str]`
  - `enrichment_funding: list[str]`
  - `enrichment_mesh_terms: list[str]`
  - `enrichment_tldr: str | None`
  - `enrichment_influential_citation_count: int | None`
  - `enrichment_references_count: int | None`
  - `enrichment_license: str | None`
  - `enrichment_venue: str | None`
  - `enrichment_failure: str`

---

### Requirement: Enrichment worker uses KNOWN_ATTRIBUTE_KEYS sentinel for documentation
The system SHALL expose a `KNOWN_ATTRIBUTE_KEYS: frozenset[str]` constant in `backend/schemas.py` containing all top-level keys from `EntityAttributesDict`. This constant SHALL be importable for use in test assertions.

#### Scenario: KNOWN_ATTRIBUTE_KEYS matches TypedDict
- **WHEN** `KNOWN_ATTRIBUTE_KEYS` is imported from `backend.schemas`
- **THEN** it SHALL contain exactly the same key names as the `EntityAttributesDict` fields

---

### Requirement: Test assertion catches undocumented attribute keys
The system SHALL include a test helper or assertion in `backend/tests/test_entity_metadata_contract.py` that verifies no enrichment result writes an undocumented top-level key into `attributes_json`.

#### Scenario: Known keys pass the assertion
- **WHEN** the enrichment worker writes only keys in `KNOWN_ATTRIBUTE_KEYS` to `attributes_json`
- **THEN** the test assertion passes without error

#### Scenario: Unknown key triggers test warning or failure
- **WHEN** an `attributes_json` dict contains a top-level key not in `KNOWN_ATTRIBUTE_KEYS`
- **THEN** the test assertion reports the unknown key so the developer can update the contract

---

### Requirement: enrichment_worker imports EnrichmentStatus from schemas
The enrichment worker SHALL import `EnrichmentStatus` from `backend.schemas` and use its constants wherever it reads or writes `enrichment_status` on a `RawEntity` instance.

#### Scenario: Worker sets completed status via enum
- **WHEN** enrichment succeeds and the worker updates an entity
- **THEN** `entity.enrichment_status` SHALL be set to `EnrichmentStatus.completed` (not the bare string `"completed"`)

#### Scenario: Worker sets failed status via enum
- **WHEN** enrichment fails after all retries
- **THEN** `entity.enrichment_status` SHALL be set to `EnrichmentStatus.failed`
