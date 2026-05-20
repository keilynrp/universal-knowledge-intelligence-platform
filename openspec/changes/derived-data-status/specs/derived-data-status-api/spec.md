## ADDED Requirements

### Requirement: DerivedResourceStatus schema is defined in one module
The system SHALL define the `DerivedResourceStatus` schema in `backend/services/derived_status_service.py`. The six tracked resources SHALL be:
- `enrichment` — entity-level enrichment pipeline
- `graph` — bibliometric/semantic graph materialization
- `semantic_keyword_signals` — keyword opportunity signal engine
- `rag_index` — RAG/ChromaDB vector index
- `executive_dashboard_snapshot` — aggregated dashboard KPI cache
- `report_readiness` — report artifact availability

The seven canonical status values SHALL be:
- `missing` — no derived data has ever been built
- `pending` — a build job is queued but not started
- `processing` — a build job is actively running
- `ready` — derived data is current relative to source records
- `stale` — derived data exists but source records have changed since last build
- `failed` — the most recent build attempt failed
- `unknown` — status cannot be determined (e.g., external index unreachable)

No other module SHALL define or validate derived resource status strings independently.

#### Scenario: All six resources are present in every status response
- **WHEN** `GET /derived-status/{domain_id}` is called for any domain
- **THEN** the response includes exactly six resource entries: `enrichment`, `graph`, `semantic_keyword_signals`, `rag_index`, `executive_dashboard_snapshot`, `report_readiness`
- **AND** each entry contains `status`, `updated_at`, `source_count`, `derived_count`, `last_error`, `can_rebuild`, and `rebuild_endpoint`

#### Scenario: Status value is always one of the canonical seven
- **WHEN** any resource status is computed
- **THEN** the `status` field is one of: `missing`, `pending`, `processing`, `ready`, `stale`, `failed`, `unknown`
- **AND** no other string values appear in the `status` field

### Requirement: derived_status_service computes status from existing DB state
The system SHALL provide a `DerivedStatusService` class in `backend/services/derived_status_service.py` that computes the status of each resource by reading existing DB columns and counts. The service SHALL NOT modify any data or trigger any pipeline.

Computation rules per resource:

**enrichment**:
- `source_count` = total entities in domain
- `derived_count` = entities where `enrichment_status IN ("completed", "done", "enriched")`
- `status` = `missing` if `source_count == 0`; `ready` if `derived_count == source_count`; `stale` if `derived_count < source_count` and `derived_count > 0`; `missing` if `derived_count == 0`

**graph**:
- `source_count` = total entities in domain
- `derived_count` = distinct entity IDs that appear in at least one `EntityRelationship` row scoped to the domain
- `status` = `missing` if no relationships exist; `ready` if relationships exist and were built after the last ingest timestamp; `stale` otherwise

**semantic_keyword_signals**:
- `source_count` = total entities in domain
- `derived_count` = entities with non-null `enrichment_concepts` in domain
- `status` = `missing` if `derived_count == 0`; `ready` if signals were materialized after last enrichment; `stale` otherwise

**rag_index**:
- `derived_count` = count returned by ChromaDB collection for the domain (or `0` if unreachable)
- `status` = `unknown` if ChromaDB client is unreachable; `missing` if `derived_count == 0`; `ready` or `stale` based on entity count comparison

**executive_dashboard_snapshot**:
- Computed from the analytics cache freshness: `ready` if cache is warm (within TTL), `stale` if cache is cold, `missing` if no cache entry exists for the domain

**report_readiness**:
- `derived_count` = count of `Report` rows for the domain with `status = "completed"`
- `status` = `missing` if no reports exist; `ready` if at least one completed report exists; `stale` if source entity count has grown since last report generation

#### Scenario: Enrichment fully complete marks resource as ready
- **WHEN** all entities in a domain have `enrichment_status = "completed"`
- **THEN** `DerivedStatusService.compute("enrichment", scope, db)` returns `status = "ready"`
- **AND** `derived_count == source_count`

#### Scenario: Partial enrichment marks resource as stale
- **WHEN** some but not all entities in a domain have been enriched
- **THEN** `DerivedStatusService.compute("enrichment", scope, db)` returns `status = "stale"`
- **AND** `derived_count < source_count`

#### Scenario: No entities in domain returns missing
- **WHEN** the domain has zero entities
- **THEN** all resources return `status = "missing"` and `source_count = 0`

#### Scenario: ChromaDB unreachable returns unknown for rag_index
- **WHEN** the ChromaDB client raises a connection error during status computation
- **THEN** `rag_index` status is `"unknown"`
- **AND** `last_error` contains a human-readable description of the failure
- **AND** no exception propagates to the caller

### Requirement: GET /derived-status/{domain_id} returns full status bundle
The system SHALL expose `GET /derived-status/{domain_id}` that returns a JSON object containing the status of all six tracked resources for the given domain scope. The endpoint SHALL:
- Accept any valid `DomainScope` value for `domain_id` (normalized via `parse_scope`)
- Require authentication (any authenticated user)
- Return HTTP 200 with the status bundle on success
- Cache the computed result with a 30-second TTL per (domain_id, org_id) pair
- Return HTTP 404 only if the domain does not exist in the registry; `"all"` scope is always valid

Response shape:
```json
{
  "domain_id": "domain:science",
  "computed_at": "2026-05-20T17:00:00Z",
  "resources": {
    "enrichment": {
      "status": "stale",
      "updated_at": "2026-05-20T15:00:00Z",
      "source_count": 1500,
      "derived_count": 1200,
      "last_error": null,
      "can_rebuild": true,
      "rebuild_endpoint": "/enrich/bulk?domain_id=domain:science"
    },
    "graph": { "...": "..." },
    "semantic_keyword_signals": { "...": "..." },
    "rag_index": { "...": "..." },
    "executive_dashboard_snapshot": { "...": "..." },
    "report_readiness": { "...": "..." }
  }
}
```

#### Scenario: Endpoint returns all six resources
- **WHEN** `GET /derived-status/domain:science` is called by an authenticated user
- **THEN** the response contains `resources` with exactly six keys
- **AND** the response is HTTP 200

#### Scenario: Endpoint accepts all scope values
- **WHEN** `GET /derived-status/all` is called
- **THEN** the response aggregates status across all domains
- **AND** the response is HTTP 200

#### Scenario: Endpoint is cached
- **WHEN** the same endpoint is called twice within 30 seconds for the same domain
- **THEN** the second response is served from cache without re-querying the DB
- **AND** `computed_at` is identical in both responses

#### Scenario: Unknown domain returns 404
- **WHEN** `GET /derived-status/domain:nonexistent` is called and `nonexistent` is not in the domain registry
- **THEN** the response is HTTP 404

### Requirement: Enrichment completion propagates staleness to downstream resources
After a batch of entities completes enrichment, the system SHALL log a staleness signal for `graph`, `semantic_keyword_signals`, `rag_index`, and `executive_dashboard_snapshot`. In v1, the staleness signal is captured by invalidating the derived-status cache for the affected domain so the next `GET /derived-status` call recomputes fresh state.

The enrichment worker SHALL NOT write to a new status table — staleness is implicit in the count comparison performed at query time.

#### Scenario: Enrichment batch completes and cache is invalidated
- **WHEN** `enrichment_worker.py` marks a batch of entities as `completed`
- **THEN** the derived-status TTL cache entry for that domain is invalidated
- **AND** the next call to `GET /derived-status/{domain_id}` reflects the updated enrichment counts

### Requirement: Graph materialization propagates staleness to dashboard and RAG
After graph materialization completes for a domain, the system SHALL invalidate the derived-status cache entry for that domain so `executive_dashboard_snapshot` and `rag_index` reflect their post-graph state on the next status poll.

#### Scenario: Graph materialization completes and cache is invalidated
- **WHEN** `graph_materializer.py` completes building relationships for a domain
- **THEN** the derived-status cache for that domain is invalidated
- **AND** the next status poll reflects updated graph relationship counts

### Requirement: CI tests cover all status computation paths
The project SHALL include unit tests in `backend/tests/test_derived_status.py` covering:
- All six resources returning `missing` for an empty domain
- `enrichment` returning `ready`, `stale`, and `missing` based on entity counts
- `rag_index` returning `unknown` when ChromaDB is unreachable (mocked)
- The endpoint returning HTTP 200 with all six keys
- Cache hit behavior

#### Scenario: Tests pass on empty domain
- **WHEN** the test DB contains no entities for the tested domain
- **THEN** all six resources return `status = "missing"`

#### Scenario: Tests verify cache TTL behavior
- **WHEN** the endpoint is called twice within the TTL window
- **THEN** the second response returns the same `computed_at` timestamp
