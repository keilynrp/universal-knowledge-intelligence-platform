## Why

UKIP currently starts enrichment, scheduled-import, and scheduled-report loops
inside the backend web process. This constrains the backend to one replica and
couples API availability to durable work. A web restart can interrupt work, and
horizontal API scaling can create duplicate scheduler execution.

This is incompatible with the reliability and recoverability expected in a
high-assurance enterprise deployment.

## What Changes

- Introduce a durable job envelope and state machine.
- Separate API producers, scheduler/dispatcher, and worker processes.
- Require tenant-scoped idempotency, retries, leases, cancellation, and replay.
- Add queue and worker health, SLOs, alerts, and audit events.
- Migrate enrichment, scheduled imports, and scheduled reports incrementally.
- Preserve an explicit rollback path during rollout.

## Non-goals

- Exactly-once execution.
- Migrating every background task in one release.
- Multi-region active-active execution.
- Selecting a broker before workload and recovery requirements are accepted.

## Capabilities

### New

- `durable-background-job-contract`
- `external-job-worker-runtime`
- `job-operability-and-recovery`

### Modified

- `enrichment-scheduler-service`
- scheduled import runtime
- scheduled report runtime
- production deployment topology

## Success Criteria

- Accepted jobs remain durable across API and worker restarts.
- Duplicate delivery does not duplicate side effects.
- Tenant scope is enforced through the full job lifecycle.
- Terminal failures are visible, attributable, and replayable through an
  authorized audited action.
- API, scheduler, and workers can scale independently.
- Rollout and rollback are exercised.
- The runtime completes a 14-day production-like observation window.

