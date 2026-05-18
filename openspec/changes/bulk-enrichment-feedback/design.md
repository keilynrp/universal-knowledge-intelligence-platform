## Context

The bulk enrichment system currently works as follows:
1. Frontend calls `POST /enrich/bulk-ids` with selected entity IDs
2. Backend sets all records to `enrichment_status = "pending"` and returns `{ queued: N }`
3. A background async worker claims one record at a time (2s delay between each), enriches via OpenAlex/Scopus/WoS/Scholar cascade, and sets status to `completed` or `failed`
4. Frontend polls the entity list every 5s and the global enrichment stats every 5s

The problem: the user sees a single toast ("Queued N") and then must watch the table for badge changes. No aggregate progress, no completion event, no failure diagnostics.

## Goals / Non-Goals

**Goals:**
- Provide real-time batch progress visibility without adding infrastructure (no WebSockets, no Redis)
- Show a persistent progress indicator with live counts (processed/total)
- Notify the user when their batch completes with a success/failure summary
- Surface per-record failure diagnostics inline in the entity table
- Prevent accidental re-enrichment of already-completed records

**Non-Goals:**
- Server-Sent Events (SSE) or WebSocket push — overkill for current scale; polling is sufficient
- Per-record progress toast (too noisy) — aggregate only
- Batch queuing system or job IDs persisted to DB — lightweight in-memory tracking is sufficient
- Modifying the background worker's processing speed or parallelism

## Decisions

### 1. Batch tracking: in-memory dict vs DB column

**Decision**: In-memory dict keyed by batch UUID, stored in a module-level `_active_batches` dict in `enrichment_worker.py`.

**Rationale**: Batches are short-lived (seconds to minutes). Persisting them adds schema complexity for no benefit. If the server restarts mid-batch, the frontend's polling will detect "no active batch" and stop gracefully.

**Alternative considered**: Adding `enrichment_batch_id` column to RawEntity — rejected because it adds a migration, clutters the model, and batches don't need historical tracking.

### 2. Progress endpoint: dedicated route

**Decision**: `POST /enrich/progress` accepts `{ ids: [...] }` and returns `{ total, pending, processing, completed, failed }` by querying status counts for those IDs.

**Rationale**: Stateless — no batch ID needed. The frontend already knows which IDs it sent. A simple count query on the same IDs provides accurate progress without any new state.

**Alternative considered**: Batch UUID approach — rejected because it requires the frontend to store a batch ID and introduces lifecycle management (expiry, cleanup).

### 3. Frontend progress UI: persistent toast with auto-dismiss

**Decision**: A floating progress toast (bottom-right) that:
- Appears immediately after bulk-ids returns
- Polls `/enrich/progress` every 3s with the original IDs
- Shows "Enriching 5/10..." with a progress bar
- On completion: morphs into success/failure summary toast (auto-dismiss after 8s)
- Clicking the summary toast scrolls/navigates to failed records if any

**Rationale**: Non-blocking, visible without occupying main UI real estate, familiar pattern.

### 4. Row-level indicators: CSS animation on status badge

**Decision**: Entity rows with `enrichment_status === "pending" || "processing"` get an animated pulse ring on their status badge. No separate spinner component needed — a `animate-pulse` class on the existing badge suffices.

**Rationale**: Minimal code change, visually clear, no layout shift.

### 5. Failure details: expandable inline panel

**Decision**: Failed rows show a clickable error icon next to the badge. Clicking reveals an inline panel below the row with: failure code, evidence text, and actionable recommendations (from `attributes_json.enrichment_failure`).

**Rationale**: Keeps context in place (no modal interrupting flow). The data already exists in `attributes_json` — just needs a UI surface.

### 6. Guard against re-enrichment of completed records

**Decision**: Add `force: boolean = False` param to `POST /enrich/bulk-ids`. Without `force`, filter out records where `enrichment_status == "completed"`. Return `{ queued: N, skipped: M }`.

**Rationale**: Prevents accidental re-processing. Frontend can show "N queued, M already enriched (skipped)" in the initial toast.

## Risks / Trade-offs

- **[Stale progress on server restart]** → If server restarts mid-batch, the progress endpoint returns current DB state (some completed, some reset to pending). Frontend handles gracefully by stopping poll when no pending/processing remain.
- **[Large batch polling cost]** → Querying status for 500 IDs every 3s is a simple `WHERE id IN (...)` with count — negligible on SQLite for <10k records.
- **[Race between poll stop and worker]** → Frontend may stop polling 1 cycle before the last record finishes. Mitigated by the completion toast checking `pending + processing === 0`.
