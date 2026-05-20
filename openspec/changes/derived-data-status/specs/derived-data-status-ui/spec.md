## ADDED Requirements

### Requirement: DerivedStatusPanel component renders per-resource status indicators
The system SHALL provide a `DerivedStatusPanel` React component at `frontend/app/components/DerivedStatusPanel.tsx` that renders a compact health indicator grid for all six tracked derived resources. The component SHALL:
- Accept a `domainId: string` prop (the active domain scope)
- Display one row per resource: `enrichment`, `graph`, `semantic_keyword_signals`, `rag_index`, `executive_dashboard_snapshot`, `report_readiness`
- Render a colored status badge for each resource reflecting one of the seven canonical status values
- Show `source_count` and `derived_count` for resources where those values are meaningful
- Show `updated_at` formatted as a relative timestamp (e.g., "2 hours ago")
- Show a "Rebuild" button for any resource where `can_rebuild = true` and `status` is not `processing` or `pending`
- Show a spinner/loading state while the initial fetch is in flight
- Show an error state if the endpoint returns non-200

Status badge color mapping SHALL be:
- `ready` → green
- `stale` → amber/yellow
- `missing` → gray
- `pending` → blue (pulsing)
- `processing` → blue (pulsing)
- `failed` → red
- `unknown` → orange

#### Scenario: Panel renders all six resources on load
- **WHEN** `DerivedStatusPanel` is mounted with a valid `domainId`
- **THEN** the panel displays exactly six resource rows
- **AND** each row shows a status badge, resource name, and relevant metadata

#### Scenario: Ready resource shows green badge
- **WHEN** a resource has `status = "ready"`
- **THEN** the status badge renders with green styling
- **AND** no "Rebuild" button is shown for that resource

#### Scenario: Stale resource shows Rebuild button
- **WHEN** a resource has `status = "stale"` and `can_rebuild = true`
- **THEN** a "Rebuild" button is shown for that resource
- **AND** clicking it triggers a POST request to `rebuild_endpoint`

#### Scenario: Processing resource shows pulsing indicator
- **WHEN** a resource has `status = "processing"` or `status = "pending"`
- **THEN** the status badge pulses to indicate active work
- **AND** no "Rebuild" button is shown for that resource

#### Scenario: Unknown status shows informational message
- **WHEN** a resource has `status = "unknown"`
- **THEN** the status badge renders in orange
- **AND** the `last_error` field content is shown as a tooltip or inline note

### Requirement: DerivedStatusPanel polls at adaptive intervals
The component SHALL poll `GET /derived-status/{domainId}` at:
- **30-second intervals** when any resource has `status` in `{"pending", "processing"}`
- **5-minute intervals** otherwise (passive refresh)

Polling SHALL stop when the component unmounts. The polling interval SHALL be recomputed after each successful response.

#### Scenario: Active polling when a resource is processing
- **WHEN** any resource in the response has `status = "processing"`
- **THEN** the next poll fires after 30 seconds
- **AND** the panel visually reflects the updated state on each poll

#### Scenario: Passive polling when all resources are settled
- **WHEN** no resource has `status` in `{"pending", "processing"}`
- **THEN** the next poll fires after 5 minutes
- **AND** polling continues until the component unmounts

#### Scenario: Polling stops on unmount
- **WHEN** the component that renders `DerivedStatusPanel` unmounts
- **THEN** no further fetch requests are sent to `GET /derived-status/{domainId}`

### Requirement: DerivedStatusPanel is embedded in Executive Dashboard and home page
The `DerivedStatusPanel` SHALL be embedded in:
- `frontend/app/analytics/dashboard/page.tsx` — below the KPI summary row, above the timeline chart
- `frontend/app/page.tsx` — in a collapsible "Data Readiness" section visible to authenticated users

The panel SHALL be conditionally rendered only when `activeDomainId` is not `"all"` (aggregate scope shows no per-domain status).

#### Scenario: Panel appears on Executive Dashboard for a specific domain
- **WHEN** an authenticated user opens the Executive Dashboard with a specific domain selected
- **THEN** `DerivedStatusPanel` renders below the KPI summary row
- **AND** it shows the status for that domain's six resources

#### Scenario: Panel hidden in all-domains view
- **WHEN** the active domain scope is `"all"`
- **THEN** `DerivedStatusPanel` is not rendered on the dashboard or home page

#### Scenario: Panel appears in collapsible section on home page
- **WHEN** an authenticated user visits the home page with a specific domain active
- **THEN** a "Data Readiness" section is visible
- **AND** it can be expanded or collapsed to show/hide `DerivedStatusPanel`

### Requirement: Rebuild button triggers the resource's rebuild endpoint
When the user clicks "Rebuild" on a resource row, the component SHALL:
- Immediately set that resource row to a local `pending` state (optimistic UI)
- Issue a `POST` request to the `rebuild_endpoint` URL from the status response
- On success: show a toast/banner "Rebuild started" and switch to active polling
- On failure: revert the row to its previous status and show an error message

#### Scenario: Rebuild button click starts the rebuild
- **WHEN** the user clicks "Rebuild" on a resource with `can_rebuild = true`
- **THEN** a POST request is sent to `rebuild_endpoint`
- **AND** the row immediately shows a pending indicator

#### Scenario: Rebuild failure reverts the row
- **WHEN** the POST to `rebuild_endpoint` returns a non-200 status
- **THEN** the resource row reverts to its pre-click status
- **AND** an error message is displayed to the user

### Requirement: Resource display names are human-readable
The UI SHALL map internal resource keys to human-readable display labels:
- `enrichment` → "Entity Enrichment"
- `graph` → "Knowledge Graph"
- `semantic_keyword_signals` → "Keyword Signals"
- `rag_index` → "RAG Index"
- `executive_dashboard_snapshot` → "Dashboard Snapshot"
- `report_readiness` → "Report Readiness"

#### Scenario: Resource names are shown in readable form
- **WHEN** `DerivedStatusPanel` renders resource rows
- **THEN** each row shows the human-readable label, not the raw resource key
