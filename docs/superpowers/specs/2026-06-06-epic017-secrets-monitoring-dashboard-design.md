# EPIC-017 — Secrets Monitoring Dashboard (read-only Security tab)

**Date:** 2026-06-06
**Status:** Design approved, ready for implementation planning
**Related:** EPIC-017 Secrets & Credential Rotation (merged PRs #48–#52); `docs/operating/SECRETS_ROTATION_RUNBOOK.md`

## Problem

EPIC-017 shipped secrets rotation (MultiFernet dual-key, JWT multi-key verify, the
`secret_rotation_events` evidence table, the off-HTTP re-encrypt script, and the
`secrets` ops health check). Today the only way an operator can see rotation
health or the evidence trail is via the terminal (`/ops/checks` curl or a direct
Python call). After the first production rotation (2026-06-06), the operator asked
for a dashboard surface, restricted to `admin`/`super_admin`, to view this without
the terminal.

## Scope

**In scope (read-only, secrets-only):**
- A new **Security** tab under Settings, visible only to `admin` and `super_admin`.
- A status card for the `secrets` operational check (ok / warning / critical) with
  its human-readable details.
- A table of the secret-rotation evidence trail (`secret_rotation_events`).
- A static callout linking to the rotation runbook, stating that the actual key
  swap happens in Dokploy (no in-app action).

**Explicitly out of scope (by design):**
- Any action that performs or triggers rotation over HTTP. The runbook mandates
  rotation actions stay off-HTTP; the key swap is an environment-variable change +
  redeploy in Dokploy. This dashboard is **monitoring only**.
- Account unlock / user management (the operator chose monitoring-only scope).
- The other operational checks (`database`, `migrations`, schedulers,
  `ops_alerting`). This panel is focused on secrets; broadening it is a future,
  separate iteration.

## Design

### Chosen approach

A dedicated read-only endpoint `GET /ops/secrets` that returns, in a single round
trip, the `secrets` check plus the recent rotation events. This keeps the secrets
concern isolated, avoids over-fetching the other `/ops/checks` results, and reuses
the already-tested `_secrets_check` logic.

(Considered and rejected: reusing `/ops/checks` and filtering client-side —
over-fetches and leaks unrelated check data to the tab; frontend-only — impossible,
no evidence endpoint exists.)

### Backend

**1. New helper in `backend/secret_rotation.py`:**

```python
def list_rotation_events(db: Session, limit: int = 20) -> list[models.SecretRotationEvent]:
    """Recent rotation evidence, newest first. Read-only."""
```
Orders by `rotated_at` desc, applies `limit`. No change to existing write logic.

**2. New schemas in `backend/schemas.py`:**

- `SecretRotationEventResponse` — `id: int`, `secret_name: str`, `rotated_at: datetime`,
  `operator: str`, `rows_reencrypted: int | None`, `old_key_fingerprint: str | None`,
  `new_key_fingerprint: str | None`, `notes: str | None`. `model_config =
  ConfigDict(from_attributes=True)`.
- `SecretsCheckResponse` — `id: str`, `status: str`, `summary: str`,
  `details: dict[str, Any]`. Mirrors the dict shape returned by `_secrets_check`.
- `SecretsOverviewResponse` — `check: SecretsCheckResponse`,
  `events: list[SecretRotationEventResponse]`.

**3. New endpoint in `backend/routers/analytics_ops.py`:**

```python
@router.get("/ops/secrets", tags=["analytics"])
def secrets_overview(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
) -> schemas.SecretsOverviewResponse:
    from backend.ops_checks import _secrets_check
    from backend.secret_rotation import list_rotation_events
    return {
        "check": _secrets_check(db),
        "events": list_rotation_events(db, limit=20),
    }
```

Read-only; same `require_role("super_admin", "admin")` gate as the existing
`/ops/checks`. Reuses `_secrets_check(db)` (tested) and the new helper.

### Frontend

**1. New `frontend/app/settings/SecurityTab.tsx`** following the `AccountTab`
pattern (same card classes, dark-mode support, `apiFetch`, `useToast`,
`useLanguage`):

- **Status card:** `Badge` colored by `check.status` — ok=green, warning=amber,
  critical=red — plus the `check.summary` and a readable grid of `check.details`:
  `jwt_insecure_default`, `encryption_key_configured`,
  `encryption_retiring_keys_present`, `jwt_retiring_keys_present`,
  `stale_rotations`, `max_age_days`. A **Refresh** button re-fetches.
- **Evidence table:** columns — date (`rotated_at`), secret (`secret_name`),
  operator, rows re-encrypted, fingerprints (`old → new`), notes. Empty state when
  `events` is empty.
- **Runbook callout:** static text pointing to
  `docs/operating/SECRETS_ROTATION_RUNBOOK.md`, noting the key swap is performed in
  Dokploy (env var + redeploy), not from this UI.

Data source: a single `apiFetch("/ops/secrets")` on mount and on Refresh.

**2. Wiring in `frontend/app/settings/page.tsx`:**
- Extend the `Tab` type union with `"security"`.
- Add `...(isAdmin ? [{ id: "security", label: t("settings.tab.security") }] : [])`
  to the `tabs` array.
- Render `{tab === "security" && isAdmin && <SecurityTab toast={toast} />}`.

**3. i18n:** add the new keys (tab label, card titles, detail labels, table
headers, empty state, runbook callout) in both EN and ES, matching the existing
`t(...)` key convention.

### Error handling

- **Backend:** `require_role` returns 403 for `viewer`/`editor`; DB failures bubble
  to FastAPI's generic 500, consistent with sibling endpoints.
- **Frontend:** `try/catch` around `apiFetch` with an error toast; loading spinner
  while fetching; empty state for the evidence table. Mirrors `AccountTab`.

### Testing

- **Backend (CI-gated, `pytest backend/tests/`):** new
  `backend/tests/test_ops_secrets_endpoint.py`:
  - `admin` and `super_admin` → 200 with `{check, events}` shape; `check.id ==
    "secrets"`.
  - `viewer` and `editor` → 403.
  - After seeding an event via `record_rotation_event`, it appears in `events` with
    correct fields.
  - Reuses existing fixtures (`auth_headers`, `editor_headers`, `viewer_headers`).
- **Frontend:** no new test framework introduced (repo relies on backend tests +
  manual verification); the tab is verified visually after build.

## Files touched

| File | Change |
|------|--------|
| `backend/secret_rotation.py` | + `list_rotation_events` helper |
| `backend/schemas.py` | + `SecretRotationEventResponse`, `SecretsCheckResponse`, `SecretsOverviewResponse` |
| `backend/routers/analytics_ops.py` | + `GET /ops/secrets` endpoint |
| `frontend/app/settings/SecurityTab.tsx` | new component |
| `frontend/app/settings/page.tsx` | tab wiring (type union, tabs array, render) |
| i18n files (EN + ES) | new translation keys |
| `backend/tests/test_ops_secrets_endpoint.py` | new test file |

## Gotchas

- `_secrets_check` is module-private (`_`-prefixed) in `ops_checks.py` but is
  imported and reused intentionally; keep the import local to the endpoint to avoid
  widening the module's public surface.
- The endpoint returns the check dict verbatim; `SecretsCheckResponse.details` is a
  free-form dict so future additions to `_secrets_check` details don't break the
  schema.
- Fingerprints are non-reversible `sha256:<12hex>` truncations — safe to render.
- Reuse the existing `/ops/checks` role gate exactly (`require_role("super_admin",
  "admin")`) for consistency.
