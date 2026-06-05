# Data Lifecycle Policy

EPIC-016. Defines how UKIP handles the lifecycle of tenant data: retention,
subject export, deletion (right to erasure), and the evidence retained for each.

> Status: **baseline (Slice 1)**. The audit backbone and policy are in place;
> export (US-071), deletion (US-072), and retention purge (US-073) land in
> subsequent slices. This document is updated as each control ships.

## Scope

Applies to all tenant-scoped data (anything carrying `org_id`) plus derived
stores: the ChromaDB vector index, DuckDB cubes, and Redis cache.

## Roles

- **Tenant admin** (`admin` / `super_admin`): may request export or deletion for
  subjects within their organization.
- **Platform operator**: owns the retention schedule and incident response.

## Subject types

| subject_type | Meaning |
|---|---|
| `org` | All data for an organization (tenant). |
| `user` | Data owned by a specific user within the active org. |
| `entity_owner` | Data tied to a specific data subject / owner reference. |

## Controls

### Audit evidence (Slice 1 — implemented)

Every lifecycle action records a `DataLifecycleEvent` (tenant-scoped): action,
subject, requester, status, request scope, and per-store evidence counts on
completion. Events are immutable application records and never cross orgs.

### Export / DSAR (Slice 2 — planned)

Admins can export all data for a subject as a portable bundle. The operation is
recorded as an `export` event with per-surface counts.

### Deletion / right to erasure (Slice 3 — planned)

Admins can erase a subject's data with a complete cascade across every store.
Recorded as a `deletion` event with before/after counts per store. Deletion is
destructive and irreversible; it requires explicit confirmation and an
expected-count echo.

### Retention purge (Slice 4 — planned)

Data past its retention window is purged on a schedule, recorded as a `purge`
event. Retention windows are configurable per data class and tenant/plan.

## Retention windows (baseline — to be finalized in Slice 4)

| Data class | Default retention | Notes |
|---|---|---|
| Operational audit events | Indefinite | Required as compliance evidence. |
| Imported / enriched entities | Tenant-defined | Owned by the tenant; purge on request or window. |
| Agentic chat traces | 90 days (proposed) | Revisit with customer requirements. |
| Derived caches / cubes | Rebuildable | Safe to purge; regenerated on demand. |

## Evidence retention

Lifecycle events (the audit trail itself) are retained as the proof that an
export or erasure occurred, even after the underlying data is deleted.
