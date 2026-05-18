## Why

Users who trigger bulk enrichment on selected records have no visibility into the process. The only feedback is a single toast at queue time ("Queued N records") and silent status badge changes in the entity table. There is no progress indicator, no completion summary, and no proactive notification when records fail. This makes the feature feel broken or unresponsive, especially for batches that take 20-60+ seconds to process.

## What Changes

- Add a backend endpoint to report enrichment job progress (processed/total/succeeded/failed) for a given batch of entity IDs
- Introduce a persistent progress toast in the frontend that shows live enrichment progress ("Enriching 3/10...")
- Show a completion notification with success/failure summary when the batch finishes
- Add per-row animated indicators (pulse/spinner) for entities in "pending" or "processing" state
- Surface enrichment failure details (code, evidence, recommendations) via a tooltip or expandable panel on failed rows
- Fix: prevent re-queueing already-completed records unless explicitly requested (add optional `force` flag)

## Capabilities

### New Capabilities
- `enrichment-progress-tracking`: Backend batch progress query and frontend real-time progress UI (toast + row indicators + completion summary)
- `enrichment-failure-details`: Accessible display of per-record failure diagnostics (code, evidence, recommendations) in the entity table

### Modified Capabilities

## Impact

- **Backend**: `backend/routers/entities.py` — new `POST /enrich/bulk-ids/progress` endpoint; modify `POST /enrich/bulk-ids` to tag batch and add `force` param
- **Frontend**: `useEntityTableController.ts` — progress polling loop; `EntityTableBulkActions.tsx` — progress toast component; `EntityTableContent.tsx` — row-level indicators and failure tooltip
- **Models**: May add `enrichment_batch_id` column or use in-memory tracking (design decision)
- **No new dependencies** — uses existing polling infrastructure
