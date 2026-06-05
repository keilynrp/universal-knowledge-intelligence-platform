# EPIC-016 — Data Lifecycle & Privacy Controls — Blueprint

Construction plan for the P0 `data_lifecycle_controls` gap. Each slice is a
single verified PR (same cadence as EPIC-012). Briefs are self-contained so a
fresh agent can execute each one cold.

**Foundation to reuse (do not re-derive):**
- `backend/tenant_access.py` — `resolve_request_org_id`, `scope_query_to_org`,
  `get_scoped_record`, `persisted_org_id`, `LEGACY_GLOBAL_ORG_ID`.
- EPIC-012 surface inventory — every model carrying `org_id` (grep `org_id = Column`
  in `backend/models.py`) is in scope for export/deletion. Non-DB stores:
  ChromaDB (`VectorStoreService`, doc ids `entity-<id>`), DuckDB cubes, Redis cache.
- Admin gating pattern: `require_role("super_admin", "admin")`.

**Dependency order:** US-070 → (US-071, US-072 can parallelize) → US-073.
US-073's purge reuses the cascade executor from US-072.

---

## Slice 1 — US-070: Lifecycle audit foundation + policy

**Goal:** a tenant-scoped audit record for every lifecycle action, plus the
written policy. Nothing destructive yet — this is the evidence backbone the
other slices write to.

**Create / modify:**
- `backend/models.py` — `DataLifecycleEvent`: `id`, `org_id` (FK, indexed,
  nullable for legacy-global), `action` (`export|deletion|purge`), `subject_type`
  (`org|user|entity_owner`), `subject_ref` (str), `requested_by` (user id),
  `status` (`started|completed|failed`), `scope_json` (Text), `evidence_json`
  (Text, counts per store), `created_at`, `completed_at`.
- `alembic/versions/*_data_lifecycle_events.py` — idempotent (guard column/index/FK
  like the EPIC-012 migrations); functional `downgrade`.
- `backend/services/data_lifecycle.py` — `record_event(...)` / `complete_event(...)`
  helpers writing `DataLifecycleEvent`.
- `docs/operating/DATA_LIFECYCLE_POLICY.md` — retention periods per data class,
  deletion SLA, what evidence is retained, who owns the process.

**Tests:** `test_epic016_data_lifecycle_audit.py` — event is written org-scoped;
legacy-global persists as NULL; cross-org cannot read another org's events.

**Acceptance:** event model + migration round-trip (SQLite + Postgres), policy doc
merged, helper covered by tests.

---

## Slice 2 — US-071: Subject/tenant export (DSAR)

**Goal:** an admin can export *all* data for a subject (org / user / entity owner)
as a portable bundle.

**Create / modify:**
- `backend/services/data_lifecycle.py` — `collect_subject_data(db, org_id, subject)`
  that walks the EPIC-012 surface inventory (org-scoped) and returns a dict keyed
  by surface. Include ChromaDB metadata for the subject's entities.
- `backend/routers/data_lifecycle.py` — `POST /admin/data-export`
  (`require_role("super_admin","admin")`, resolves org_id, writes a
  `DataLifecycleEvent` action=export). Returns a JSON bundle (reuse CSV/Excel
  exporters where useful); stream for large bundles.
- Register router in `backend/main.py`.

**Tests:** `test_epic016_data_lifecycle_export.py` — bundle contains the subject's
rows from each surface; a different org's export never includes this subject's
data; non-admin → 403; event recorded.

**Acceptance:** export returns a complete, org-scoped bundle; evidence event written.

---

## Slice 3 — US-072: Deletion / right to erasure (cascade)

**Goal:** an admin can erase a subject's data with a complete cascade and evidence.
Highest-risk slice — destructive and irreversible.

**Create / modify:**
- `backend/services/data_lifecycle.py` — `delete_subject_data(db, org_id, subject)`:
  cascade across every org-scoped surface **and** ChromaDB
  (`VectorStoreService.delete_document` per `entity-<id>`), DuckDB cubes, Redis
  cache keys. Return per-store deleted counts for the evidence record.
- `backend/routers/data_lifecycle.py` — `POST /admin/data-deletion`
  (admin, org-scoped). Strong confirmation (explicit subject + expected-count echo,
  like the harmonization apply prompt). Writes `DataLifecycleEvent` action=deletion
  with before/after counts. Consider soft-delete + grace period before hard purge.

**Tests:** `test_epic016_data_lifecycle_deletion.py` — **the critical test**: after
deletion, assert **zero** subject records remain in *every* store (DB surfaces +
ChromaDB query by org/entity). Cross-org deletion of another tenant's subject → 404.
Non-admin → 403. Evidence event has per-store counts.

**Acceptance:** cascade leaves no residue in any store; evidence complete; cross-tenant
safe.

---

## Slice 4 — US-073: Retention purge job + config

**Goal:** data past its retention window is purged automatically, with evidence.

**Create / modify:**
- Retention config (per data class / per tenant or plan) — extend existing settings
  or a new config surface.
- A scheduled purge that reuses `delete_subject_data` / a `purge_expired(db)` routine,
  writing `DataLifecycleEvent` action=purge. Align with US-042 background-job
  externalization (do not deepen in-process scheduling debt).
- Admin visibility: list recent lifecycle events (`GET /admin/data-lifecycle/events`,
  org-scoped).

**Tests:** `test_epic016_data_lifecycle_retention.py` — expired rows purged, fresh rows
kept, purge evidence written, org-scoped.

**Acceptance:** retention purge runs on schedule with evidence; events listable by admins.

---

## Closeout

When all four slices merge:
- Update `backend/enterprise_readiness.py`: move `data_lifecycle_controls` from open
  gaps to `RESOLVED_GAPS` (with PR evidence), same pattern used for `tenant_isolation`.
- Update `GET /ops/enterprise-readiness` expectations in tests if counts change.
- Add a deploy note if the purge job needs enabling per environment.
