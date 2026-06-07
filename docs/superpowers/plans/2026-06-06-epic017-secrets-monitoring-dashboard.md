# EPIC-017 Secrets Monitoring Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only "Security" tab under Settings (admin/super_admin only) that shows the `secrets` ops health check and the secret-rotation evidence trail.

**Architecture:** One new read-only endpoint `GET /ops/secrets` returns the `secrets` check (reusing `_secrets_check`) plus the recent `secret_rotation_events` in a single round trip. A new `SecurityTab.tsx` renders a status card + evidence table, wired into the existing Settings tab system, gated by `isAdmin`.

**Tech Stack:** FastAPI + SQLAlchemy (backend), Next.js + React + Tailwind (frontend), pytest (tests). Spec: `docs/superpowers/specs/2026-06-06-epic017-secrets-monitoring-dashboard-design.md`.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/secret_rotation.py` | + `list_rotation_events(db, limit)` read helper |
| `backend/schemas.py` | + `SecretRotationEventResponse`, `SecretsCheckResponse`, `SecretsOverviewResponse` |
| `backend/routers/analytics_ops.py` | + `GET /ops/secrets` endpoint |
| `backend/tests/test_ops_secrets_endpoint.py` | new endpoint + helper tests |
| `frontend/app/settings/SecurityTab.tsx` | new read-only component (status card + evidence table) |
| `frontend/app/settings/page.tsx` | tab wiring (type union, tabs array, render) |
| `frontend/app/i18n/translations.ts` | new EN + ES keys |

**Conventions to follow (verified in codebase):**
- Tests use `client`, `auth_headers` (super_admin), `editor_headers`, `viewer_headers`, `db_session` fixtures from `conftest.py`.
- Endpoint role gate: `Depends(require_role("super_admin", "admin"))` (matches existing `/ops/checks` at `analytics_ops.py:185`).
- `_secrets_check(db)` lives in `backend/ops_checks.py:279` and returns `{id, status, summary, details}`.
- Frontend tab pattern: `page.tsx` spreads `...(isAdmin ? [{...}] : [])` into `tabs` and renders `{tab === "x" && isAdmin && <Comp/>}`.
- `Badge` variants: `success | warning | error | info | purple | default` (`components/ui/Badge.tsx`).

---

## Task 1: Backend helper — `list_rotation_events`

**Files:**
- Modify: `backend/secret_rotation.py` (append after `last_rotation_at`)
- Test: `backend/tests/test_ops_secrets_endpoint.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ops_secrets_endpoint.py`:

```python
from datetime import datetime, timezone, timedelta

from backend import models, secret_rotation as sr


def _seed_event(db, secret_name="ENCRYPTION_KEY", operator="alice", rows=3, when=None):
    ev = models.SecretRotationEvent(
        secret_name=secret_name,
        operator=operator,
        rows_reencrypted=rows,
        old_key_fingerprint="sha256:aaaaaaaaaaaa",
        new_key_fingerprint="sha256:bbbbbbbbbbbb",
        notes="test",
        rotated_at=when or datetime.now(timezone.utc),
    )
    db.add(ev)
    db.commit()
    return ev


def test_list_rotation_events_newest_first_and_limit(db_session):
    _seed_event(db_session, operator="old", when=datetime.now(timezone.utc) - timedelta(days=5))
    _seed_event(db_session, operator="new", when=datetime.now(timezone.utc))

    events = sr.list_rotation_events(db_session, limit=20)
    assert [e.operator for e in events] == ["new", "old"]

    limited = sr.list_rotation_events(db_session, limit=1)
    assert len(limited) == 1
    assert limited[0].operator == "new"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_ops_secrets_endpoint.py::test_list_rotation_events_newest_first_and_limit -v`
Expected: FAIL — `AttributeError: module 'backend.secret_rotation' has no attribute 'list_rotation_events'`

- [ ] **Step 3: Write minimal implementation**

In `backend/secret_rotation.py`, add after `last_rotation_at` (around line 35):

```python
def list_rotation_events(db: Session, limit: int = 20) -> list[models.SecretRotationEvent]:
    """Recent rotation evidence, newest first. Read-only."""
    return (
        db.query(models.SecretRotationEvent)
        .order_by(models.SecretRotationEvent.rotated_at.desc())
        .limit(limit)
        .all()
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_ops_secrets_endpoint.py::test_list_rotation_events_newest_first_and_limit -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/secret_rotation.py backend/tests/test_ops_secrets_endpoint.py
git commit -m "feat: add list_rotation_events helper for secrets dashboard"
```

---

## Task 2: Backend schemas

**Files:**
- Modify: `backend/schemas.py` (add near other response models)

- [ ] **Step 1: Add schemas**

In `backend/schemas.py`, ensure `from typing import Any` is imported (it likely already imports from typing — add `Any` if missing), then add:

```python
class SecretRotationEventResponse(BaseModel):
    id: int
    secret_name: str
    rotated_at: datetime
    operator: str
    rows_reencrypted: Optional[int] = None
    old_key_fingerprint: Optional[str] = None
    new_key_fingerprint: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SecretsCheckResponse(BaseModel):
    id: str
    status: str
    summary: str
    details: dict[str, Any]


class SecretsOverviewResponse(BaseModel):
    check: SecretsCheckResponse
    events: list[SecretRotationEventResponse]
```

> Note: `BaseModel`, `Field`, `ConfigDict`, `Optional`, `datetime` are already used in this file (see existing models). Only `Any` may need adding to the `typing` import.

- [ ] **Step 2: Verify it imports cleanly**

Run: `.venv/Scripts/python -c "from backend import schemas; print(schemas.SecretsOverviewResponse.model_json_schema()['title'])"`
Expected: prints `SecretsOverviewResponse` (no import error)

- [ ] **Step 3: Commit**

```bash
git add backend/schemas.py
git commit -m "feat: add secrets overview response schemas"
```

---

## Task 3: Backend endpoint — `GET /ops/secrets`

**Files:**
- Modify: `backend/routers/analytics_ops.py` (add endpoint after `/ops/checks/run`, ~line 202; add `schemas` import)
- Test: `backend/tests/test_ops_secrets_endpoint.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ops_secrets_endpoint.py`:

```python
def test_secrets_overview_admin_ok(client, auth_headers, db_session):
    _seed_event(db_session, operator="keilyn")
    resp = client.get("/ops/secrets", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["check"]["id"] == "secrets"
    assert body["check"]["status"] in {"ok", "warning", "critical"}
    assert "encryption_key_configured" in body["check"]["details"]
    assert any(e["operator"] == "keilyn" for e in body["events"])
    ev = body["events"][0]
    assert {"secret_name", "rotated_at", "rows_reencrypted",
            "old_key_fingerprint", "new_key_fingerprint"} <= set(ev.keys())


def test_secrets_overview_forbidden_for_editor(client, editor_headers):
    resp = client.get("/ops/secrets", headers=editor_headers)
    assert resp.status_code == 403


def test_secrets_overview_forbidden_for_viewer(client, viewer_headers):
    resp = client.get("/ops/secrets", headers=viewer_headers)
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest backend/tests/test_ops_secrets_endpoint.py -v -k overview`
Expected: FAIL — 404 (route not found) on the admin test

- [ ] **Step 3: Add the `schemas` import**

In `backend/routers/analytics_ops.py`, change the existing line:
```python
from backend.schemas import EnrichmentStatus
```
to:
```python
from backend import schemas
from backend.schemas import EnrichmentStatus
```

- [ ] **Step 4: Add the endpoint**

In `backend/routers/analytics_ops.py`, after the `/ops/checks/run` endpoint (after line ~202), add:

```python
@router.get("/ops/secrets", tags=["analytics"], response_model=schemas.SecretsOverviewResponse)
def secrets_overview(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Read-only secrets rotation health + evidence trail (EPIC-017 dashboard)."""
    from backend.ops_checks import _secrets_check
    from backend.secret_rotation import list_rotation_events
    return {
        "check": _secrets_check(db),
        "events": list_rotation_events(db, limit=20),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_ops_secrets_endpoint.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 6: Run the broader ops test to confirm no regression**

Run: `.venv/Scripts/python -m pytest backend/tests/test_sprint104_ops_checks.py backend/tests/test_epic017_secrets_check.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/routers/analytics_ops.py backend/tests/test_ops_secrets_endpoint.py
git commit -m "feat: add GET /ops/secrets read-only endpoint for secrets dashboard"
```

---

## Task 4: i18n keys

**Files:**
- Modify: `frontend/app/i18n/translations.ts`

- [ ] **Step 1: Locate the EN and ES blocks**

Open `frontend/app/i18n/translations.ts` and find the existing `settings.tab.account` key in both the English and Spanish maps (search for `"settings.tab.account"`).

- [ ] **Step 2: Add keys to BOTH locales**

Add these keys alongside the existing `settings.tab.*` and `settings.*` keys. **English** values:

```
"settings.tab.security": "Security",
"settings.security.title": "Secret rotation health",
"settings.security.subtitle": "Read-only. The key swap itself is performed in Dokploy (env var + redeploy), not here.",
"settings.security.status_title": "Secrets check",
"settings.security.refresh": "Refresh",
"settings.security.detail.jwt_default": "JWT signing key",
"settings.security.detail.jwt_default.secure": "Strong (not default)",
"settings.security.detail.jwt_default.insecure": "INSECURE DEFAULT",
"settings.security.detail.enc_key": "Encryption key configured",
"settings.security.detail.enc_retiring": "Encryption retiring keys present",
"settings.security.detail.jwt_retiring": "JWT retiring keys present",
"settings.security.detail.stale": "Stale rotations",
"settings.security.detail.cadence": "Rotation cadence (days)",
"settings.security.detail.none": "None",
"settings.security.evidence_title": "Rotation evidence",
"settings.security.col.date": "Date",
"settings.security.col.secret": "Secret",
"settings.security.col.operator": "Operator",
"settings.security.col.rows": "Rows re-encrypted",
"settings.security.col.fingerprints": "Key fingerprints",
"settings.security.col.notes": "Notes",
"settings.security.empty": "No rotations recorded yet.",
"settings.security.runbook": "Rotation procedure: docs/operating/SECRETS_ROTATION_RUNBOOK.md",
"settings.security.load_error": "Could not load secrets status.",
"settings.security.yes": "Yes",
"settings.security.no": "No",
```

**Spanish** values:

```
"settings.tab.security": "Seguridad",
"settings.security.title": "Salud de rotación de secretos",
"settings.security.subtitle": "Solo lectura. El cambio de llave se realiza en Dokploy (variable de entorno + redeploy), no aquí.",
"settings.security.status_title": "Check de secretos",
"settings.security.refresh": "Refrescar",
"settings.security.detail.jwt_default": "Llave de firma JWT",
"settings.security.detail.jwt_default.secure": "Fuerte (no default)",
"settings.security.detail.jwt_default.insecure": "DEFAULT INSEGURO",
"settings.security.detail.enc_key": "Llave de cifrado configurada",
"settings.security.detail.enc_retiring": "Llaves de retiro de cifrado presentes",
"settings.security.detail.jwt_retiring": "Llaves de retiro JWT presentes",
"settings.security.detail.stale": "Rotaciones vencidas",
"settings.security.detail.cadence": "Cadencia de rotación (días)",
"settings.security.detail.none": "Ninguna",
"settings.security.evidence_title": "Evidencia de rotaciones",
"settings.security.col.date": "Fecha",
"settings.security.col.secret": "Secreto",
"settings.security.col.operator": "Operador",
"settings.security.col.rows": "Filas re-encriptadas",
"settings.security.col.fingerprints": "Fingerprints de llaves",
"settings.security.col.notes": "Notas",
"settings.security.empty": "Aún no hay rotaciones registradas.",
"settings.security.runbook": "Procedimiento de rotación: docs/operating/SECRETS_ROTATION_RUNBOOK.md",
"settings.security.load_error": "No se pudo cargar el estado de secretos.",
"settings.security.yes": "Sí",
"settings.security.no": "No",
```

- [ ] **Step 3: Verify the file still parses (typecheck)**

Run (from `frontend/`): `npx tsc --noEmit --pretty false 2>&1 | head -20`
Expected: no new errors referencing `translations.ts`

- [ ] **Step 4: Commit**

```bash
git add frontend/app/i18n/translations.ts
git commit -m "feat: add i18n keys for security settings tab (EN+ES)"
```

---

## Task 5: Frontend component — `SecurityTab.tsx`

**Files:**
- Create: `frontend/app/settings/SecurityTab.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/app/settings/SecurityTab.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import { Badge, type ToastVariant } from "../components/ui";
import { apiFetch } from "@/lib/api";

type SecretsCheck = {
    id: string;
    status: "ok" | "warning" | "critical" | string;
    summary: string;
    details: {
        jwt_insecure_default?: boolean;
        encryption_key_configured?: boolean;
        encryption_retiring_keys_present?: boolean;
        jwt_retiring_keys_present?: boolean;
        stale_rotations?: string[];
        max_age_days?: number;
    };
};

type RotationEvent = {
    id: number;
    secret_name: string;
    rotated_at: string;
    operator: string;
    rows_reencrypted: number | null;
    old_key_fingerprint: string | null;
    new_key_fingerprint: string | null;
    notes: string | null;
};

type Overview = { check: SecretsCheck; events: RotationEvent[] };

const STATUS_VARIANT: Record<string, "success" | "warning" | "error" | "default"> = {
    ok: "success",
    warning: "warning",
    critical: "error",
};

function getErrorMessage(error: unknown, fallback: string) {
    return error instanceof Error ? error.message : fallback;
}

export default function SecurityTab({ toast }: { toast: (msg: string, v?: ToastVariant) => void }) {
    const { t } = useLanguage();
    const [data, setData] = useState<Overview | null>(null);
    const [loading, setLoading] = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch("/ops/secrets");
            if (!res.ok) {
                const body = await res.json().catch(() => ({ detail: t("settings.security.load_error") })) as { detail?: string };
                throw new Error(body.detail || t("settings.security.load_error"));
            }
            setData(await res.json() as Overview);
        } catch (error: unknown) {
            toast(getErrorMessage(error, t("settings.security.load_error")), "error");
        } finally {
            setLoading(false);
        }
    }, [t, toast]);

    useEffect(() => { void load(); }, [load]);

    const check = data?.check;
    const details = check?.details ?? {};
    const yn = (v: boolean | undefined) => (v ? t("settings.security.yes") : t("settings.security.no"));

    return (
        <div className="space-y-4">
            {/* Status card */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <div className="mb-4 flex items-center justify-between">
                    <h3 className="text-base font-semibold text-gray-900 dark:text-white">{t("settings.security.status_title")}</h3>
                    <div className="flex items-center gap-3">
                        {check && (
                            <Badge variant={STATUS_VARIANT[check.status] ?? "default"} dot>
                                {check.status.toUpperCase()}
                            </Badge>
                        )}
                        <button
                            onClick={() => void load()}
                            disabled={loading}
                            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                        >
                            {t("settings.security.refresh")}
                        </button>
                    </div>
                </div>

                <p className="mb-1 text-sm text-gray-500 dark:text-gray-400">{t("settings.security.subtitle")}</p>
                {check && <p className="mb-4 text-sm font-medium text-gray-800 dark:text-gray-200">{check.summary}</p>}

                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <DetailRow label={t("settings.security.detail.jwt_default")}
                        value={details.jwt_insecure_default
                            ? t("settings.security.detail.jwt_default.insecure")
                            : t("settings.security.detail.jwt_default.secure")}
                        danger={details.jwt_insecure_default} />
                    <DetailRow label={t("settings.security.detail.enc_key")} value={yn(details.encryption_key_configured)} />
                    <DetailRow label={t("settings.security.detail.enc_retiring")} value={yn(details.encryption_retiring_keys_present)} />
                    <DetailRow label={t("settings.security.detail.jwt_retiring")} value={yn(details.jwt_retiring_keys_present)} />
                    <DetailRow label={t("settings.security.detail.stale")}
                        value={(details.stale_rotations && details.stale_rotations.length)
                            ? details.stale_rotations.join(", ")
                            : t("settings.security.detail.none")}
                        danger={!!(details.stale_rotations && details.stale_rotations.length)} />
                    <DetailRow label={t("settings.security.detail.cadence")} value={String(details.max_age_days ?? "—")} />
                </div>

                <p className="mt-4 text-xs text-gray-400">{t("settings.security.runbook")}</p>
            </div>

            {/* Evidence table */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
                <h3 className="mb-4 text-base font-semibold text-gray-900 dark:text-white">{t("settings.security.evidence_title")}</h3>
                {!data || data.events.length === 0 ? (
                    <p className="text-sm text-gray-500 dark:text-gray-400">{t("settings.security.empty")}</p>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead>
                                <tr className="border-b border-gray-200 text-xs uppercase tracking-wider text-gray-400 dark:border-gray-800">
                                    <th className="py-2 pr-4">{t("settings.security.col.date")}</th>
                                    <th className="py-2 pr-4">{t("settings.security.col.secret")}</th>
                                    <th className="py-2 pr-4">{t("settings.security.col.operator")}</th>
                                    <th className="py-2 pr-4">{t("settings.security.col.rows")}</th>
                                    <th className="py-2 pr-4">{t("settings.security.col.fingerprints")}</th>
                                    <th className="py-2">{t("settings.security.col.notes")}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.events.map(ev => (
                                    <tr key={ev.id} className="border-b border-gray-100 text-gray-700 dark:border-gray-800/60 dark:text-gray-300">
                                        <td className="py-2 pr-4 whitespace-nowrap">{new Date(ev.rotated_at).toLocaleString()}</td>
                                        <td className="py-2 pr-4 font-mono text-xs">{ev.secret_name}</td>
                                        <td className="py-2 pr-4">{ev.operator}</td>
                                        <td className="py-2 pr-4">{ev.rows_reencrypted ?? "—"}</td>
                                        <td className="py-2 pr-4 font-mono text-[11px] text-gray-500">
                                            {(ev.old_key_fingerprint ?? "—") + " → " + (ev.new_key_fingerprint ?? "—")}
                                        </td>
                                        <td className="py-2 text-gray-500">{ev.notes ?? "—"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}

function DetailRow({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
    return (
        <div className="flex items-center justify-between rounded-xl border border-gray-100 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-800/50">
            <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400">{label}</span>
            <span className={`text-sm font-medium ${danger ? "text-red-600 dark:text-red-400" : "text-gray-800 dark:text-gray-200"}`}>{value}</span>
        </div>
    );
}
```

- [ ] **Step 2: Typecheck**

Run (from `frontend/`): `npx tsc --noEmit --pretty false 2>&1 | grep -i "SecurityTab" | head`
Expected: no errors referencing `SecurityTab.tsx`

- [ ] **Step 3: Commit**

```bash
git add frontend/app/settings/SecurityTab.tsx
git commit -m "feat: add read-only SecurityTab component for secrets dashboard"
```

---

## Task 6: Wire the tab into Settings

**Files:**
- Modify: `frontend/app/settings/page.tsx`

- [ ] **Step 1: Import the component**

After the `import AssistantGuardrailsTab from "./AssistantGuardrailsTab";` line, add:
```tsx
import SecurityTab from "./SecurityTab";
```

- [ ] **Step 2: Extend the `Tab` type union**

Change the `Tab` type (line ~22) to include `"security"`:
```tsx
type Tab = "preferences" | "account" | "users" | "auth" | "webhooks" | "notifications" | "branding" | "workspace_reset" | "field_rules" | "assistant_guardrails" | "data_fixes" | "security";
```

- [ ] **Step 3: Add the tab entry (admin-gated)**

In the `tabs` array, after the `assistant_guardrails` entry, add:
```tsx
        ...(isAdmin ? [{ id: "security", label: t("settings.tab.security") }] : []),
```

- [ ] **Step 4: Add the render branch**

After the `assistant_guardrails` render line, add:
```tsx
            {tab === "security" && isAdmin && <SecurityTab toast={toast} />}
```

- [ ] **Step 5: Typecheck**

Run (from `frontend/`): `npx tsc --noEmit --pretty false 2>&1 | grep -iE "page.tsx|SecurityTab" | head`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add frontend/app/settings/page.tsx
git commit -m "feat: wire Security tab into settings (admin-gated)"
```

---

## Task 7: Full verification

- [ ] **Step 1: Run the full backend test suite for the touched areas**

Run: `.venv/Scripts/python -m pytest backend/tests/test_ops_secrets_endpoint.py backend/tests/test_sprint104_ops_checks.py backend/tests/test_epic017_secrets_check.py backend/tests/test_epic017_rotation_evidence.py -v`
Expected: all PASS

- [ ] **Step 2: Frontend production build**

Run (from `frontend/`): `npm run build`
Expected: build succeeds, no type errors

- [ ] **Step 3: Manual smoke (optional, if a dev server is available)**

Log in as a super_admin, open Settings → Security tab. Confirm: the status card shows the `secrets` check with a colored badge, the detail grid renders, and the evidence table lists rotation events (or the empty state). Confirm the tab is NOT visible to a viewer/editor account.

- [ ] **Step 4: Final commit (if any uncommitted changes remain)**

```bash
git add -A
git commit -m "chore: secrets monitoring dashboard verification"
```

---

## Notes

- **DRY:** the endpoint reuses `_secrets_check` and the new `list_rotation_events`; no logic is duplicated.
- **YAGNI:** read-only, secrets-only, no rotation actions over HTTP (per the runbook's off-HTTP mandate).
- **CI scope:** only `pytest backend/tests/` is gated in CI; top-level `tests/` and `.worktrees/` are out of scope (known repo gotcha).
- **`_secrets_check` import is local** to the endpoint to avoid widening `ops_checks` public surface.
- **Windows/PowerShell shell note:** the typecheck steps pipe `tsc ... | grep`. On this environment `grep` may be unavailable — substitute `Select-String` (e.g. `npx tsc --noEmit --pretty false 2>&1 | Select-String SecurityTab`) or just run `npx tsc --noEmit` and scan the output. The pytest commands use `.venv/Scripts/python` (already Windows-correct).
