## 1. Discovery and decision

- [x] 1.1 Inventory all in-process loops, producers, handlers, side effects, and tenant scopes.
- [x] 1.2 Capture workload size, duration, concurrency, retry, and payload characteristics.
- [x] 1.3 Evaluate Celery, Dramatiq, and PostgreSQL lease queue against accepted criteria.
- [x] 1.4 Record the runtime decision and rejected alternatives in an ADR.
- [x] 1.5 Complete threat model and failure-mode analysis.

## 2. Durable contract

- [x] 2.1 Add job envelope and transition model.
- [x] 2.2 Add tenant-scoped idempotency constraints.
- [x] 2.3 Add claim, lease renewal, retry, cancellation, and recovery services.
- [x] 2.4 Add sanitized audit events and retention behavior.
- [x] 2.5 Add unit and PostgreSQL concurrency tests.

## 3. Runtime and operations

- [x] 3.1 Add independently deployable worker and scheduler entrypoints.
- [x] 3.2 Add graceful drain and abandoned-lease recovery.
- [x] 3.3 Add metrics, health checks, alerts, and bounded diagnostics.
- [x] 3.4 Add operator runbook for outage, backlog, poison job, replay, and rollback.
- [x] 3.5 Add deployment topology and capacity defaults.

## 4. Incremental migration

- [ ] 4.1 Shadow-write and compare scheduled-report behavior.
- [ ] 4.2 Cut over scheduled reports behind a feature flag.
- [ ] 4.3 Shadow-write and cut over scheduled imports.
- [ ] 4.4 Shadow-write and cut over enrichment scheduling/execution.
- [ ] 4.5 Disable in-process schedulers by default.

## 5. Verification and evidence

- [ ] 5.1 Test duplicate delivery and idempotent side effects.
- [ ] 5.2 Test cross-tenant access, replay, and error metadata isolation.
- [ ] 5.3 Test API restart, worker crash, broker outage, DB outage, and recovery.
- [ ] 5.4 Test migration rollback with accepted in-flight work.
- [ ] 5.5 Complete load test and define queue-age SLOs.
- [ ] 5.6 Complete 14-day production-like observation window.
- [ ] 5.7 Publish release-scoped evidence and update ER-OPS-001 to `operated`.

