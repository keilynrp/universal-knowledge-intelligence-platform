## Context

UKIP materializes derived data through several asynchronous pipelines: enrichment (OpenAlex, Crossref, PubMed, etc.), graph materialization, semantic keyword signals, RAG indexing, executive dashboard snapshots, and report readiness. Each pipeline writes back to the database in its own way — enrichment sets `enrichment_status` per entity, graph materializer inserts `EntityRelationship` rows, RAG indexes into ChromaDB — but there is no unified place to query "what is the current state of derived data for domain X?"

The result: the UI has no way to distinguish "data is ready" from "data was never built" from "data is stale after a recent ingestion." Dashboard empty-state messages are generic; users cannot trigger a rebuild from the UI; and support requests pile up around "why is my dashboard empty?"

## Goals / Non-Goals

**Goals**
- A single `GET /derived-status/{domain_id}` endpoint that returns the status of all six tracked derived resources for a domain
- Status computed from existing DB state — no new tables required for v1
- A frontend `DerivedStatusPanel` component that renders per-resource health indicators and rebuild triggers
- Hook points in enrichment completion and graph materialization to propagate staleness downstream
- Status contract shared by backend and frontend: six fixed resources, seven canonical status values

**Non-Goals**
- Real-time push / WebSocket notifications for status changes (polling is sufficient for v1)
- Tracking derived status at the per-entity level (resource-level granularity is sufficient)
- Persistent status history or audit log for derived resources
- Status tracking for resources outside the six defined (e.g., authority resolution, harmonization)

## Decisions

### 1. Status computed at query time, not persisted

**Decision**: `DerivedDataStatus` is computed on the fly from existing DB columns on each `GET /derived-status` call, with a short TTL cache (30 s). No new status table is created in v1.

**Rationale**: Adding a new table requires a migration and a write path from every pipeline. Computed-at-query-time is simpler to implement, correct by construction, and avoids write conflicts. If latency becomes an issue, a persistent status table can be added later.

**Alternative considered**: A `DerivedResourceStatus` table with one row per (domain, resource). Rejected for v1 due to migration cost and the complexity of keeping it consistent across all write paths.

### 2. Six fixed tracked resources

**Decision**: The six resources are `enrichment`, `graph`, `semantic_keyword_signals`, `rag_index`, `executive_dashboard_snapshot`, `report_readiness`. These are defined as a Python enum-like set of constants in `derived_status_service.py`.

**Rationale**: Matches the list in `system-hardening-and-regression-control` spec. Keeping the list fixed prevents scope creep; new resources can be added explicitly when needed.

### 3. Seven canonical status values

**Decision**: `missing | pending | processing | ready | stale | failed | unknown`

- `missing` — no derived data has ever been built for this resource + domain
- `pending` — a build job is queued but has not started
- `processing` — a build job is actively running
- `ready` — derived data exists and is current relative to source records
- `stale` — derived data exists but source records have changed since it was built
- `failed` — the most recent build attempt failed with an error
- `unknown` — status cannot be determined (e.g., external index not reachable)

**Rationale**: Mirrors the spec from `system-hardening-and-regression-control`. `stale` is the key addition — it allows the UI to show "ready but outdated" without triggering a full rebuild automatically.

### 4. Staleness detection via entity count comparison

**Decision**: A resource is `stale` when `source_count` (entities in the domain) differs from `derived_count` (enriched/indexed/graphed entities) by more than a threshold (default: any delta > 0). `ready` is only returned when counts match.

**Rationale**: Simple, fast, and correct for most cases without needing a separate write path. The enrichment case is exact — `enrichment_status = "completed"` entities are counted against total. Graph and signals use relationship and signal row counts respectively.

### 5. `rebuild_endpoint` field for one-click triggers

**Decision**: Each resource in the status response includes `can_rebuild: bool` and `rebuild_endpoint: str | null`. The frontend calls the endpoint directly when the user clicks "Rebuild."

**Rationale**: Avoids coupling the status service to the pipeline services. The status service only reads; rebuild actions go through the existing router endpoints.

### 6. Frontend polling at 30-second intervals

**Decision**: `DerivedStatusPanel` polls `GET /derived-status/{domain_id}` every 30 seconds while any resource is in `pending` or `processing` state, falling back to 5-minute passive refresh otherwise.

**Rationale**: Balances freshness with server load. 30-second polling is only active when there is active work; passive refresh is cheap enough for the background case.

## Risks / Trade-offs

- **[Risk] Count-based staleness is imprecise for graph and signals**: graph relationship count and keyword signal count don't map 1:1 to entity count. → Mitigation: document that `stale` means "counts don't match" and `ready` means "last build was after last ingestion timestamp," not that every entity has a relationship. Adjust thresholds per resource.
- **[Risk] ChromaDB / RAG index is an external process**: querying it for a count may fail if it's not running. → Mitigation: return `unknown` status for `rag_index` if the ChromaDB client is unreachable; surface a clear message in the UI.
- **[Risk] Polling cost on large deployments**: 30-second polling per active user adds load. → Mitigation: cache the status response with a 30-second TTL on the backend; multiple clients hitting the endpoint within one TTL window share the same computation.

## Migration Plan

1. Create `backend/services/derived_status_service.py` — status computation for all six resources.
2. Create `backend/routers/derived_status.py` — `GET /derived-status/{domain_id}` endpoint with TTL cache.
3. Register the new router in `backend/main.py`.
4. Add staleness hooks to `backend/enrichment_worker.py` and `backend/services/graph_materializer.py` (log-only in v1; no DB writes needed since status is computed at query time).
5. Create `frontend/app/components/DerivedStatusPanel.tsx` — status widget with polling.
6. Embed `DerivedStatusPanel` in `frontend/app/analytics/dashboard/page.tsx` and `frontend/app/page.tsx`.
7. Write backend tests for `derived_status_service.py` and the endpoint.
