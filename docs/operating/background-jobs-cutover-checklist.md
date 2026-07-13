# Background Job Runtime — Cutover Checklist

> Step-by-step operational checklist to migrate each in-process background domain
> onto the durable job queue (ADR-007). Companion to
> [background-jobs-runbook.md](background-jobs-runbook.md) and
> [background-jobs-topology.md](background-jobs-topology.md). Completing this is a
> prerequisite for tasks 5.5–5.7 of `external-background-job-runtime`.

**Safety model.** Every domain defaults to `off` — the code is already in
production with **zero behavior change**. This checklist flips flags deliberately,
one domain at a time, in the order **reports → imports → enrichment** (lowest
volume/risk first). Any step is reversible by flipping the flag back.

## Flags

| Env var | Values | Default | Effect |
|---------|--------|---------|--------|
| `UKIP_JOBS_REPORTS` | `off` \| `shadow` \| `queue` | `off` | scheduled-reports domain mode |
| `UKIP_JOBS_IMPORTS` | `off` \| `shadow` \| `queue` | `off` | scheduled-imports domain mode |
| `UKIP_JOBS_ENRICHMENT` | `off` \| `shadow` \| `queue` | `off` | enrichment domain mode |
| `UKIP_INPROCESS_SCHEDULERS` | `1` \| `0` | `1` | in-process worker/scheduler loops in the API |

- `off` — in-process path only (today's behavior).
- `shadow` — in-process stays authoritative **and** a durable job is enqueued for
  parity; the shadow job performs **no** external side effect.
- `queue` — the durable worker is authoritative; the in-process path skips.

> Declare any flag you set in `docker-compose.prod.yml` / Dokploy so the value
> reaches the container (env-var/compose parity). `UKIP_INPROCESS_SCHEDULERS`
> stays `1` until the very end.

---

## Phase 0 — Pre-flight (once, before any domain)

- [ ] Confirm the durable table exists in prod: `background_jobs` (alembic head at
      or past `c1d2e3f4a5b6`). Run `alembic current` on the DB.
- [ ] Deploy at least one **worker** and exactly one **scheduler** process:
  - `python -m backend.scripts.run_job_worker` (scale ≥1; may shard with `--job-type`)
  - `python -m backend.scripts.run_job_scheduler` (**exactly one instance**)
- [ ] Verify processes are healthy: `GET /jobs/health` → `live_workers ≥ 1`,
      `status: ok`.
- [ ] Confirm baseline metrics are readable: `GET /jobs/metrics` returns depth 0.
- [ ] Confirm rollback is understood: flipping a domain flag back to `off` restores
      the in-process path immediately (no deploy needed if the var is runtime-read).

---

## Per-domain cutover (repeat for reports, then imports, then enrichment)

Replace `<DOMAIN>` with `REPORTS` / `IMPORTS` / `ENRICHMENT`.

### Step 1 — Shadow

- [ ] Set `UKIP_JOBS_<DOMAIN>=shadow`.
- [ ] Confirm effective mode reached the container (check logs / a debug echo of
      the env var). In-process execution must continue unchanged.
- [ ] Let it run ≥1 full schedule cycle. Watch:
  - `GET /jobs?job_type=<report|import|enrichment>.execute` — jobs appear as
    enqueued → claimed → **succeeded** (shadow handlers succeed as no-ops).
  - `GET /jobs/metrics` — no growing backlog; `expired_leases` stays 0.
- [ ] **Parity check** — for each due occurrence in the window, exactly one job
      exists (stable key `{domain}:{schedule_id}:{occurrence_at}`); no duplicates
      on API scale-out. The in-process side effect (the report sent / import run /
      entity enriched) still happens exactly once via the in-process path.
- [ ] **Duplicate check** — scale the API to ≥2 replicas briefly; confirm still one
      job per occurrence (no duplicate scheduler execution).
- [ ] Abort criteria: duplicate jobs per occurrence, worker backlog growth, or any
      job stuck `running` with expired lease not recovered → set back to `off`,
      investigate.

### Step 2 — Queue (cutover)

- [ ] Set `UKIP_JOBS_<DOMAIN>=queue`.
- [ ] Now the **worker** performs the real execution; the in-process path skips.
- [ ] Verify real side effects happen via the queue: a report is delivered / an
      import runs / an entity is enriched — exactly once per occurrence.
- [ ] Watch `GET /jobs/metrics` `by_type.<...>.oldest_queued_age_seconds` stays
      under the SLO (default 900s). Scale workers if it climbs.
- [ ] Confirm failures dead-letter correctly: force/observe a failure →
      `GET /jobs?status=failed` shows it with a sanitized `error_code`; it stops
      after `max_attempts` (no crash loop).
- [ ] **Recovery drill** — restart a worker mid-job; confirm the scheduler's
      `recover_abandoned_leases` requeues the in-flight job and it completes (safe
      because handlers are idempotent).
- [ ] Rollback path (if needed): set `UKIP_JOBS_<DOMAIN>=off`. In-process resumes;
      any already-accepted durable jobs remain and can drain or be cancelled.

### Step 3 — Soak

- [ ] Run the domain in `queue` for an agreed soak (e.g., 24–48h) before moving to
      the next domain. Re-check parity, backlog, failures, and recovery.

---

## Phase 4 — Disable in-process schedulers (after all three domains are `queue`)

- [ ] Confirm `UKIP_JOBS_REPORTS`, `UKIP_JOBS_IMPORTS`, `UKIP_JOBS_ENRICHMENT` are
      all `queue` and stable.
- [ ] Set `UKIP_INPROCESS_SCHEDULERS=0`. The API replicas now start **no** worker
      or scheduler loop; all durable work runs in the worker/scheduler processes.
- [ ] Verify `GET /jobs/health` still `ok` and work continues to drain.
- [ ] Confirm API can now scale horizontally with no duplicate scheduler execution.

---

## Phase 5 — Evidence (change tasks 5.5–5.7)

- [ ] **5.5** Run a load test against the queue; record throughput, runtime/wait
      distributions, and set the queue-age SLO from results (default 900s in
      `backend/jobs/metrics.py`).
- [ ] **5.6** Complete a **14-day** production-like observation window: no data
      loss across restarts, no duplicate side effects, tenant scope intact,
      terminal failures visible/attributable/replayable, independent scaling
      exercised.
- [ ] **5.7** Publish release-scoped evidence (metrics snapshots, drill results,
      incident notes) and update **ER-OPS-001** to `operated`.
- [ ] Archive the OpenSpec change: `openspec archive external-background-job-runtime`.

---

## Rollback summary (any time)

| Situation | Action |
|-----------|--------|
| A domain misbehaves in `shadow` | `UKIP_JOBS_<DOMAIN>=off` (no side effects were queued) |
| A domain misbehaves in `queue` | `UKIP_JOBS_<DOMAIN>=off` → in-process resumes; drain/cancel accepted jobs |
| Full rollback after disabling in-process | `UKIP_INPROCESS_SCHEDULERS=1`, then set each domain to `off` |
| Worker/scheduler down | restart; abandoned leases auto-recover on the next scheduler tick |

Rollback is a **flag flip**, never a schema change — `background_jobs` and the
`/jobs` API stay in place throughout.
