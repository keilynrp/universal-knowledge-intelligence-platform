## Why

UKIP runs multiple asynchronous materialization pipelines (enrichment, graph, semantic signals, RAG indexing, dashboard snapshots, report readiness), but exposes no unified way to know whether any of them are current. Users see empty dashboards, stale KPIs, and missing graph data with no explanation — and support calls repeatedly ask "why is my dashboard empty after I enriched records?"

## What Changes

- **Introduce a `DerivedDataStatus` contract**: six tracked resources per domain/org scope — `enrichment`, `graph`, `semantic_keyword_signals`, `rag_index`, `executive_dashboard_snapshot`, `report_readiness` — each with a canonical status value and metadata fields.
- **Backend status service**: a pure read-model service (`backend/services/derived_status_service.py`) that computes the current status of each resource by inspecting DB state without touching the materialization pipelines themselves.
- **API endpoint**: `GET /derived-status/{domain_id}` returns the full status bundle; used by the frontend status panel.
- **Status propagation hooks**: enrichment completion and graph materialization mark downstream resources `stale` so the UI can show freshness correctly without polling every component independently.
- **Frontend status panel**: a compact widget on the Executive Dashboard and home page that surfaces readiness per resource and offers a one-click rebuild trigger where applicable.
- **No new dependencies** — status computation uses existing DB queries and SQLAlchemy models.

## Capabilities

### New Capabilities

- `derived-data-status-api`: Backend service + endpoint that computes and returns the derived data status bundle for a given domain/org scope. Covers all six tracked resources with status, updated_at, source_count, derived_count, last_error, can_rebuild, and rebuild_endpoint fields.
- `derived-data-status-ui`: Frontend status panel component (`DerivedStatusPanel`) that renders per-resource readiness indicators and rebuild triggers. Embedded in the Executive Dashboard and home page.

### Modified Capabilities

- `system-hardening-and-regression-control`: Derived data status contract satisfies item 2 of the progressive hardening sequence.

## Impact

- **New file**: `backend/services/derived_status_service.py` — status computation logic
- **New file**: `backend/routers/derived_status.py` — `GET /derived-status/{domain_id}` endpoint
- **Modified**: `backend/enrichment_worker.py` — emit stale signal for downstream resources after enrichment batch completes
- **Modified**: `backend/services/graph_materializer.py` — emit stale signal for `executive_dashboard_snapshot` and `rag_index` after graph is built
- **New frontend**: `frontend/app/components/DerivedStatusPanel.tsx` — compact status widget
- **Modified frontend**: `frontend/app/analytics/dashboard/page.tsx`, `frontend/app/page.tsx` — embed status panel
- **No database migration** — status is computed at query time from existing columns; no new tables required for the initial implementation
- **No new Python dependencies** — uses SQLAlchemy + existing models
