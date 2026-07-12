# Background Job Runtime — Deployment Topology & Capacity

> Deployment shape and capacity defaults for the durable job runtime (ADR-007).
> Satisfies Phase 3 task 3.5. Final numbers are set from the observation window
> (Phase 5); values here are safe starting defaults.

## Topology

```
                 ┌──────────────┐
   clients ────► │  API (N≥2)   │  enqueues jobs; NO worker/scheduler loop
                 └──────┬───────┘
                        │ writes
                 ┌──────▼───────────┐
                 │  PostgreSQL      │  background_jobs (durable queue + state)
                 └──────▲───────────┘
          claims │      │ promote/recover
        ┌────────┴──┐  ┌┴──────────────┐
        │ Worker ×M │  │ Scheduler ×1  │  (singleton dispatcher)
        └───────────┘  └───────────────┘
```

- **API**: ≥2 replicas for availability. Runs no background loop, so scaling it
  never duplicates scheduled work.
- **Worker**: M replicas (start M=2), scaled by queue-age SLO. May be sharded by
  `--job-type` for isolation of a heavy or sensitive type.
- **Scheduler**: exactly **1** replica. Its work (promote retries, recover leases)
  is idempotent, but a singleton avoids redundant scans and log noise.

## Capacity defaults (initial)

| Setting | Default | Notes |
|---------|---------|-------|
| Worker replicas | 2 | scale on `oldest_queued_age_seconds` |
| Worker poll interval | 2s | `--poll` |
| Lease duration | 60s | `--lease`; must exceed p99 handler time |
| Scheduler interval | 5s | `--interval` |
| Queue-age SLO | 900s | `metrics.DEFAULT_QUEUE_AGE_SLO_SECONDS` |
| Worker-stale threshold | 120s | heartbeat liveness |
| Max attempts (per job) | 3 | per-enqueue override |
| Retry backoff | 10s·2^(n-1), cap 3600s | exponential |

## Sizing guidance

- **Lease > handler p99.** If handlers can exceed the lease, either raise the
  lease or add mid-handler `renew_lease`; otherwise a slow job is recovered and
  re-run (safe because handlers are idempotent, but wasteful).
- **Throughput** is DB-bound. A single Postgres serves UKIP's low-to-moderate,
  I/O-bound workload comfortably; revisit only if `queued` depth grows under
  adequate worker count (indicates DB contention, not worker starvation).
- **Provider limits** (enrichment) cap effective throughput regardless of worker
  count — the circuit breaker (ADR-004) stays authoritative.

## Alerts

| Condition | Signal | Action |
|-----------|--------|--------|
| Workers down with backlog | `health.reasons` has `no_live_workers_with_backlog` | restart workers |
| Queue age over SLO | `queue_age_slo_breached` | add workers / investigate provider |
| Expired leases present | `expired_leases_present` | ensure scheduler is running |
| Terminal-failure spike | `GET /jobs?status=failed` growth | inspect poison input, replay after fix |
