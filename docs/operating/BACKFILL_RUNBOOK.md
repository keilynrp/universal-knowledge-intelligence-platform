# Backfill Runbook — `nif_bayes` & `work_type` (Dokploy)

Operator playbook for populating two enrichment fields on **existing** records that
were enriched before the features shipped. Both are **idempotent, org-scoped, and
safe to re-run** — they only touch rows that are still missing the value and never
overwrite populated rows.

| Field | Script | Affects | Populates |
|-------|--------|---------|-----------|
| `nif_bayes` + 95% CI | `backend.scripts.backfill_nif_bayes` | `journal_metrics` rows | Bayesian NIF (`nif_bayes`, `nif_ci_low`, `nif_ci_high`) + `works_2yr` |
| `work_type` | `backend.scripts.backfill_work_type` | `raw_entities` with a DOI | `enrichment_work_type` (OpenAlex `work.type`) |

Until these run, the UI degrades silently: NIF (Bayes) card hidden / `—`; work-type
facet bucket shows **"Sin clasificar"** and badges are hidden. No errors.

---

## Preconditions

1. **The code is deployed.** Confirm prod is on a commit that includes both features:
   - `work_type` merged in `94354aa` (#93) + Core-Fields row `ea0e1fc` (#94).
   - `nif_bayes` merged in `83f96af` (#90).
   Verify via the build-commit in the served HTML, or `GET /health` / `GET /openapi.json`.
2. **Migrations are at head.** Single Alembic head is `e6f7a8b9c0d2`. The backend
   entrypoint runs `alembic upgrade head` on boot; confirm the deploy came up healthy.
3. **Off-peak window.** Both scripts call the OpenAlex API once per item. Use
   `--delay` to stay polite (OpenAlex throttles aggressively; see #87/#88).

---

## How to get a shell (Dokploy)

⚠️ Per the established Dokploy gotchas (see SECRETS_ROTATION_RUNBOOK.md):
- The Dokploy web **Terminal attaches *inside* the running `ukip-backend` container** —
  there is **no `docker` CLI** in there. Run `python` directly.
- **Pasting multi-line commands mangles them** → use **single-line commands only**.
- The container `WORKDIR` is **`/app`**; `python` is the system Python 3.13 (no venv);
  modules are invoked as `python -m backend.scripts.<name>`.
- All prod env vars (DATABASE_URL → Postgres, OpenAlex, Redis) are already present in
  the shell — no need to export anything.

Steps: Dokploy → project → **ukip-backend** service → **Terminal** tab → you land at a
shell in `/app`.

---

## Step 1 — Sanity check (read-only, ~5s)

Confirm you're in the right place, DB is reachable, and see how much is pending:

```bash
python -c "import os,backend.database as d; from sqlalchemy import text; c=d.SessionLocal(); print('DB', os.environ.get('DATABASE_URL','?')[:24]); print('journals missing nif_bayes:', c.execute(text('SELECT count(*) FROM journal_metrics WHERE nif_bayes IS NULL')).scalar()); print('entities missing work_type (have DOI):', c.execute(text(\"SELECT count(*) FROM raw_entities WHERE enrichment_work_type IS NULL AND enrichment_doi IS NOT NULL\")).scalar()); c.close()"
```

If `DB` shows `sqlite` you are NOT in the prod container — stop and re-open the
correct service terminal. (SQLite is never prod.)

---

## Step 2 — Backfill `nif_bayes` (journals; small set, ~270 rows)

Run with `--refresh` so the Redis-backed OpenAlex source cache is cleared first
(drops stale pre-`works_2yr` dicts, per #89), and a polite delay:

```bash
python -m backend.scripts.backfill_nif_bayes --refresh --delay 0.2
```

Expected final line: `nif_bayes recomputed for <N> journals`.

- Org-scoped variant (one tenant): add `--org-id <N>`.
- Safe to re-run. If interrupted, just run it again.

---

## Step 3 — Backfill `work_type` (entities; can be large)

This iterates every entity that has a DOI but no `work_type`, one OpenAlex call
each — potentially thousands. **Use a delay** and expect it to take a while.

```bash
python -m backend.scripts.backfill_work_type --delay 0.2
```

Expected final line: `work_type backfilled for <N> entities`.

- Org-scoped variant: add `--org-id <N>` (recommended first run — do one org, verify,
  then the rest).
- Idempotent: only `enrichment_work_type IS NULL` rows with a DOI are touched, so a
  re-run after an interruption resumes where it left off.
- If OpenAlex starts 429-ing, increase `--delay` (e.g. `0.5`) and re-run.

---

## Step 4 — Verify

Re-run the Step 1 sanity query — both "missing" counts should drop toward 0
(some rows legitimately stay null: journals OpenAlex can't resolve, entities
without a DOI or whose work has no `type`).

In the UI:
- **Journals dashboard** (`/analytics/journals`): the **NIF (Bayes)** column shows
  values + credible-interval ranges; sortable.
- **Entity detail modal**: **NIF (Bayes)** card appears for entities with a journal;
  the **"Tipo de obra"** row shows in *Campos Principales* + header badge.
- **Entity table side panel**: the **Tipo de obra** facet shows real category counts
  (less "Sin clasificar").

---

## Rollback / safety

- Nothing to roll back — both scripts only *fill in* missing values; they never
  delete or overwrite populated data, and they commit once at the end of each run.
- Re-running is always safe and cheap (idempotent NULL-only selection).
- If a run errors midway, the partial commit is fine; just re-run to finish.
