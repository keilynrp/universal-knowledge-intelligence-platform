# Journal Metrics Surfacing (NIF + APC) — Design Spec

**Date:** 2026-06-18
**Status:** Approved (brainstorming)
**Feature:** Surface the journal Normalized Impact Factor (NIF) and APC — already computed and stored by the enrichment pipeline (PRs #77, #79) — in the UI.

## Problem

The enrichment pipeline persists journal-level metrics in the `journal_metrics` table (keyed by `issn_l`): the open Impact-Factor proxy (`two_yr_mean_citedness`), field-normalized `normalized_impact_factor` (NIF), `h_index`, APC (`apc_usd` + `apc_currency` + `apc_source`), `is_in_doaj`, and `nif_field` (OpenAlex subfield). Entities carry their journal's `issn_l` in `attributes_json`.

But there is **no read path**: the only journal endpoint is `POST /journals/normalize` (write/admin). The frontend cannot display any of this data. This spec adds the read path and two UI surfaces.

## Goals

- Expose journal metrics via a read-only, org-scoped API.
- Surface NIF + APC on the per-entity detail modal (lazy, by `issn_l`).
- Provide a journals analytics dashboard: ranking table + APC distribution + NIF-by-discipline + admin recompute trigger.
- Label the NIF honestly everywhere as an **open proxy** (OpenAlex `2yr_mean_citedness`, field-normalized) — **not** Clarivate's JIF.

## Non-goals (YAGNI / deferred)

- FX→USD conversion for DOAJ APC (stored as nominal amount + currency).
- Editing/curating journal metrics from the UI (read-only surface; recompute is the only action).
- Wiring the normalizer into the scheduler (manual/endpoint trigger stays).

## Locked decisions

- **Approach A** — aggregates computed in the backend (`GET /journals/stats`), not client-side, to scale and avoid shipping all rows.
- **RBAC** — reads use `get_current_user`; the recompute trigger reuses `require_role("super_admin", "admin")` (the existing `/journals/normalize` gate).
- **Org scoping** — every read filters by `user.org_id` (same `(org_id, issn_l)` grain as the table).
- **Charts** — Recharts (repo convention, e.g. Sprint 39 dashboard).
- **Provenance label** — one shared, reusable component used by both surfaces.

---

## Architecture

Three layers, built in dependency order as three slices.

```
journal_metrics (DB) ──> backend/routers/journals.py ──> GET /journals/{issn_l}        ──> Entity detail modal
                                                          GET /journals (paginated)     ──> Dashboard ranking table
                                                          GET /journals/stats (agg)      ──> Dashboard charts
                                          (existing)      POST /journals/normalize       ──> Dashboard admin button
```

### Slice A — Backend read-path

**New file:** `backend/routers/journals.py` (read-only router, mounted in `backend/main.py`). All endpoints depend on `get_current_user` and filter by `user.org_id`.

- `GET /journals/{issn_l}` → `JournalMetricResponse`. 404 when no row for `(org_id, issn_l)`.
- `GET /journals` → paginated list. Query params: `limit` (`Query(ge=1, le=200)`, default 50), `offset` (`ge=0`), `sort_by` ∈ {`nif`, `citedness`, `apc`, `h_index`} (default `nif`), `order` ∈ {`asc`, `desc`} (default `desc`), optional `field` (filter by `nif_field`). Emits `X-Total-Count` header (pattern from `/entities`). Invalid `sort_by`/`order` → 422.
- `GET /journals/stats` → aggregates:
  - `apc_distribution`: list of `{currency, count, min, max, median}` grouped by `apc_currency` (only rows with `apc_usd` not null).
  - `open_access_share`: `{in_doaj, total, pct}`.
  - `nif_by_field`: list of `{nif_field, journal_count, mean_nif}` grouped by `nif_field` (excluding null NIF), ordered by `mean_nif` desc.

**New schema:** `JournalMetricResponse` in `backend/schemas.py` — `issn_l`, `display_name`, `source_id`, `two_yr_mean_citedness`, `h_index`, `normalized_impact_factor`, `nif_field`, `apc_usd`, `apc_currency`, `apc_source`, `is_in_doaj`, `nif_updated_at`. Plus an `if_metric_kind` passthrough so the provenance label can read the metric kind.

**Contract fix:** add `issn_l: str` to `EntityAttributesDict` in `backend/schemas.py` (the worker writes it but it was never documented — the metadata-contract test would catch it once the journal path runs).

**Read-only service helpers** in `backend/services/journal_metrics_service.py` (extend existing): `get_journal_metric(db, org_id, issn_l)`, `list_journal_metrics(db, org_id, sort_by, order, limit, offset) -> (rows, total)`, `journal_stats(db, org_id) -> dict`. Keep SQL group-by in the service; router stays thin.

**Tests** (`backend/tests/test_journals_api.py`): single fetch + 404; pagination + `X-Total-Count` + sort validation (422 on bad `sort_by`); stats aggregates (APC buckets, OA share, NIF-by-field); **org-scoping** (org B cannot see org A's journals); auth required.

### Slice B — Entity detail modal surface

**Modify:** `frontend/app/components/EntityTableDetailsModal.tsx`.

- On open, parse `issn_l` from the entity's `attributes_json`. If present, lazy-fetch `GET /journals/{issn_l}` via the centralized `apiFetch` (`frontend/lib/api.ts`).
- Render a **"Journal" section**: NIF (with provenance badge), `two_yr_mean_citedness`, `h_index`, APC (amount + currency, "Open Access" chip when `is_in_doaj`), and the `nif_field` subfield.
- States: loading skeleton; no `issn_l` → section hidden; 404 → subtle "journal not yet enriched" note.
- Uses the shared `JournalProvenanceBadge` component.

**Tests:** component unit tests — renders metrics when data present; does not fetch when `issn_l` absent; 404 shows the subtle note.

### Slice C — Journals analytics dashboard

**New:** `frontend/app/analytics/journals/page.tsx` + components under `frontend/app/analytics/journals/`.

- **Ranking table** from `GET /journals`: columns journal, subfield, NIF, citedness, h-index, APC, OA, work-count; client controls map to `sort_by`/`order`/pagination (URL-state for shareability per repo web rules).
- **APC distribution chart** (Recharts) from `/journals/stats` `apc_distribution` + OA share.
- **NIF-by-discipline chart** (Recharts bar) from `/journals/stats` `nif_by_field`.
- **Admin "Recompute NIF" button** → `POST /journals/normalize`; visible only for admin+ (reuse the existing role-aware `useAuth`/role gate). Shows updated-count toast on success.
- Sidebar nav item + CTA from the Analytics landing, following the existing dashboard pattern.
- Governed Design System components (`SectionHeader`, etc.) to pass the frontend governance gate (no hardcoded palette classes).

**Shared:** `JournalProvenanceBadge` (and a small `formatApc` util) used by B and C — DRY.

**Tests:** ranking table renders + sort interaction; charts render from stats payload; admin button hidden for viewer, visible for admin.

---

## Data flow

1. Worker enriches a work via OpenAlex → upserts `journal_metrics` row (NIF base + APC + subfield) and tags `attributes_json.issn_l`.
2. Admin (or scheduler later) runs `POST /journals/normalize` → fills `normalized_impact_factor` per `nif_field` bucket.
3. **Modal:** entity opened → read `issn_l` → `GET /journals/{issn_l}` → render journal section.
4. **Dashboard:** `GET /journals` (table) + `GET /journals/stats` (charts) → render; admin can re-trigger normalize.

## Error handling

- Backend: 404 for missing journal; 422 for invalid sort params; reads org-scoped (no cross-org leak); empty aggregates return empty lists (not errors).
- Frontend: loading/empty/error states on every fetch; modal hides cleanly when no journal; dashboard shows empty states when no journals enriched yet; recompute button surfaces success/failure via toast.

## Testing strategy

- Backend: pytest (`backend/tests/`) — the CI gate. Cover serialization, pagination, sorting, 404, aggregates, org-scoping, auth.
- Frontend: component unit tests + preview verification (dev server: modal with real data, dashboard responsive, both themes if applicable). Respect the Design System governance gate (governed components, no hardcoded palette).

## Build order

A (backend, unblocks both surfaces) → B (modal) and C (dashboard) can follow. Each slice is independently testable and shippable.
