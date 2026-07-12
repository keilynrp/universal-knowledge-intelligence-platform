# Background Job Runtime — Operator Runbook

> Operations for the durable job runtime (ADR-007). Covers outage, backlog,
> poison jobs, replay, and rollback. Satisfies Phase 3 task 3.4.

## Processes

- **API** — enqueues jobs; runs **no** worker/scheduler loop.
- **Worker** — `python -m backend.scripts.run_job_worker` (scale horizontally).
- **Scheduler** — `python -m backend.scripts.run_job_scheduler` (**exactly one**).

Health & metrics: `GET /jobs/health` (degraded reasons), `GET /jobs/metrics`
(queue depth, oldest-queued age by type, expired leases). List/inspect via
`GET /jobs`, `GET /jobs/{job_id}`.

## Signals & scaling

- Graceful drain: send **SIGTERM** to a worker — it finishes the in-flight job,
  claims no more, then exits. Deploy rolling restarts on SIGTERM.
- Scale throughput: add worker replicas. Never run two schedulers.

## Playbooks

### Workers unavailable (`no_live_workers_with_backlog`)
1. Check worker deploy/pods are running; check `GET /jobs/health` `live_workers`.
2. Restart workers. In-flight leases on the dead workers expire and the scheduler
   recovers them (`recovered_leases`) — no manual requeue needed.

### Growing oldest-queued age (`queue_age_slo_breached`)
1. `GET /jobs/metrics` → find the `by_type` with the largest
   `oldest_queued_age_seconds`.
2. Add worker replicas (optionally a type-scoped worker: `--job-type <T>`).
3. If a provider is rate-limiting, throughput is capped by design (circuit
   breaker authoritative) — scale is not the fix; wait or raise limits.

### Poison job (repeated failures / crash loop)
1. `GET /jobs?status=failed` and inspect `error_code`/`error_detail`.
2. A job that exhausts `max_attempts` lands in `failed` (dead-letter) and stops
   retrying — it will not loop forever.
3. Fix the handler or input, then **replay** (below). Do not lower `max_attempts`
   globally to paper over a poison input.

### Replay a failed job
- `POST /jobs/{job_id}/replay` (elevated role). Creates a **new** queued job
  (`replay_of` set); the original `failed` row and its attempt history are
  preserved. The action is audited (`job.replay`).

### Cancel queued work
- `POST /jobs/{job_id}/cancel` (elevated role) for `pending|queued|retry_wait`.
  Running jobs cannot be cancelled (returns 409); let them finish or expire.

### Stuck `running` after a crash
- The scheduler's `recover_abandoned_leases` requeues `running` jobs whose
  `lease_expires_at` has passed. If the scheduler is down, start it; recovery is
  automatic on the next tick.

## Rollback

The runtime is additive and flag-gated at migration time (Phase 4). To roll back
a migrated job type: disable its feature flag so producers resume the in-process
path; drain workers (SIGTERM). Accepted in-flight jobs remain durable and can be
completed by re-enabling workers, or cancelled. The `background_jobs` table and
API stay in place — rollback is a flag flip, not a schema change.

## Retention

Terminal jobs are purged by the governed retention path
(`service.purge_terminal_jobs`, EPIC-016 data-class policy). No unbounded growth.
