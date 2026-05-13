## MODIFIED Requirements

### Requirement: Scientific Import wizard tabs
The Scientific Import wizard (`frontend/app/import/scientific/page.tsx`) SHALL present three tabs: "File Upload" (existing, tab index 0), "OpenAlex" (new, tab index 1), and "PubMed" (new, tab index 2). The existing File Upload tab SHALL remain unchanged in behavior.

#### Scenario: Default tab on page load
- **WHEN** the user navigates to `/import/scientific`
- **THEN** the "File Upload" tab is active by default
- **THEN** the existing file upload UI is displayed

#### Scenario: OpenAlex tab renders query form
- **WHEN** the user clicks the "OpenAlex" tab
- **THEN** a query builder form appears with: keyword input, optional author filter, optional ISSN filter, and a limit slider (10–1,000, default 100)
- **THEN** a "Search Preview" button is visible

#### Scenario: PubMed tab renders query form
- **WHEN** the user clicks the "PubMed" tab
- **THEN** a query builder form appears with: PubMed search query input and a limit slider (10–500, default 100)
- **THEN** a "Search Preview" button is visible

## ADDED Requirements

### Requirement: OpenAlex search-preview-import flow
The OpenAlex tab SHALL implement a three-step flow: query builder → preview of first 10 results → confirm import.

#### Scenario: Preview step shows sample records
- **WHEN** the user fills the query form and clicks "Search Preview"
- **THEN** the frontend calls `POST /import/openalex` with `{"query": ..., "limit": 10, "preview": true}`
- **THEN** the first 10 matching records are displayed in a table (title, authors, year, citations)

#### Scenario: Confirm import triggers full import
- **WHEN** the user clicks "Import <n> records" on the preview step
- **THEN** the frontend calls `POST /import/openalex` with the full limit
- **THEN** the UI shows a progress bar polling `GET /import/status/{job_id}` every 2 seconds
- **THEN** on completion, a success banner shows "Imported <n> records"

#### Scenario: Import error shown inline
- **WHEN** the import job fails (API error, network timeout)
- **THEN** an inline error banner is shown with the error message
- **THEN** the user can retry without reloading the page

### Requirement: PubMed search-preview-import flow
The PubMed tab SHALL implement the same three-step flow as the OpenAlex tab.

#### Scenario: Preview step shows sample records
- **WHEN** the user fills the PubMed query and clicks "Search Preview"
- **THEN** the frontend calls `POST /import/pubmed` with `{"query": ..., "limit": 10, "preview": true}`
- **THEN** the first 10 matching records are displayed (title, authors, year)

#### Scenario: Confirm import triggers full import
- **WHEN** the user clicks "Import <n> records"
- **THEN** the frontend calls `POST /import/pubmed` with the full limit
- **THEN** a progress bar polls `GET /import/status/{job_id}` until done

### Requirement: Import progress bar
Both the OpenAlex and PubMed tabs SHALL display a progress bar while an import job is running, driven by polling `GET /import/status/{job_id}`.

#### Scenario: Progress bar advances
- **WHEN** an import job is running and the frontend polls the status endpoint
- **THEN** the progress bar updates to reflect `progress` (0.0–1.0) from the response
- **THEN** the bar shows record count: "<inserted> / <total> records"

#### Scenario: Progress bar completes
- **WHEN** the status endpoint returns `{"status": "done"}`
- **THEN** the progress bar reaches 100% and a success message replaces it
- **THEN** polling stops
