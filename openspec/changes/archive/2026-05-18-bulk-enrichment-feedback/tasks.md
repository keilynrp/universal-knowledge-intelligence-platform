## 1. Backend: Progress Endpoint & Bulk-IDs Guard

- [x] 1.1 Add `POST /enrich/progress` endpoint in `backend/routers/entities.py` — accepts `{ ids: number[] }`, returns `{ total, pending, processing, completed, failed }` with auth required
- [x] 1.2 Modify `POST /enrich/bulk-ids` to accept optional `force: bool = False` param; skip `completed` records unless force=true; return `{ queued, skipped }`
- [x] 1.3 Write tests for `/enrich/progress` endpoint (empty ids → 422, valid ids → correct counts, auth required → 401)
- [x] 1.4 Write tests for modified `/enrich/bulk-ids` (default skips completed, force=true re-queues, all completed → queued=0 skipped=N)

## 2. Frontend: Progress Toast Component

- [x] 2.1 Create `EnrichmentProgressToast.tsx` component — floating bottom-right toast with progress bar, live "Enriching X/N..." text, and completion summary state
- [x] 2.2 Add progress polling logic in `useEntityTableController.ts` — poll `/enrich/progress` every 3s with batch IDs, update toast state, stop on completion
- [x] 2.3 Handle completion transition: morph toast into summary ("N succeeded, M failed"), auto-dismiss after 8s, include "View failed" link that applies facet filter
- [x] 2.4 Handle skipped records in initial toast: show "Queued N, skipped M (already enriched)" when `skipped > 0`
- [x] 2.5 Add i18n keys for all progress toast strings (EN + ES)

## 3. Frontend: Row-Level Indicators

- [x] 3.1 Add pulse animation class to enrichment badge in `EntityTableContent.tsx` for rows with status "pending" or "processing"
- [x] 3.2 Verify animation stops when status resolves to "completed" or "failed" during polling refresh

## 4. Frontend: Failure Diagnostics Panel

- [x] 4.1 Add clickable error icon next to enrichment badge for failed rows in `EntityTableContent.tsx`
- [x] 4.2 Create inline expandable failure panel component showing: failure code label, evidence, provider attempts, recommendations list, and record snapshot
- [x] 4.3 Add failure diagnostics section to `EntityTableDetailsModal.tsx` with "Retry Enrichment" button that calls `POST /enrich/row/{id}`
- [x] 4.4 Add i18n keys for failure panel strings (code labels, recommendations header, retry button) (EN + ES)

## 5. Integration & Cleanup

- [x] 5.1 Wire "View failed" link in completion toast to apply `enrichment_status=failed` facet filter via URL params
- [x] 5.2 Ensure progress polling interval is cleared on component unmount (cleanup in useEffect return)
- [x] 5.3 Manual E2E verification: select 5+ entities, trigger bulk enrich, observe progress toast → completion → failure details accessible
