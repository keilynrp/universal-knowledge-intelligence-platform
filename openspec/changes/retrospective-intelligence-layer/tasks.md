## 1. Architecture and governance

- [x] 1.1 Record an ADR for internal bounded context first, warehouse-ready export second, microservice extraction later.
- [x] 1.2 Inventory source workflows that create retrospective value: import, enrichment, journal metrics, authority, NIL, provenance, governance review, and user decisions.
- [x] 1.3 Define tenant, retention, deletion, and audit rules for historical records.
- [x] 1.4 Define schema versioning and payload-size limits.
- [x] 1.5 Define extraction criteria review cadence.

## 2. Historical contracts

- [x] 2.1 Add historical event envelope.
- [x] 2.2 Add snapshot envelope.
- [x] 2.3 Add event-family registry and schema-version registry.
- [x] 2.4 Add idempotency keys for scheduled snapshots and replayed writers.
- [x] 2.5 Add tests for tenant scoping, append-only writes, and schema-version validation.

## 3. Initial retrospective data

- [x] 3.1 Emit journal metric computed and recomputed events.
- [x] 3.2 Emit enrichment lifecycle events.
- [x] 3.3 Emit authority and NIL decision events. (accepted/rejected done; deferred follow-ups: candidate_created is high-volume/low-signal from batch resolution; nil_marked has no persisted decision point today — NIL is a scoring signal, needs a product decision on where it is marked.)
- [x] 3.4 Materialize journal metric, enrichment coverage, and authority readiness snapshots. (materialization service + flag-gated orchestrator; scheduler/admin-endpoint wiring is a thin follow-up.)
- [x] 3.5 Backfill bounded historical events where trustworthy source timestamps exist. (journal_metric.computed from nif_updated_at; authority.accepted from confirmed_at. Idempotent vs live emission.)

## 4. Retrospective query and UI

- [x] 4.1 Add point-in-time lookup service.
- [x] 4.2 Add current-vs-snapshot comparison service.
- [x] 4.3 Add cohort and metric time-series helpers.
- [x] 4.4 Add minimal dashboard for historical comparison.
- [x] 4.5 Add provenance explanations for retrospective values.

## 5. Warehouse export

- [x] 5.1 Define BigQuery-compatible table schemas and partitioning.
- [x] 5.2 Add export manifest format with dataset version, tenant scope, row counts, and schema version.
- [x] 5.3 Add idempotent export job for historical events.
- [x] 5.4 Add idempotent export job for snapshots and analytical marts.
- [x] 5.5 Add export validation for row counts, schema drift, and tenant isolation.

## 6. ML readiness

- [x] 6.1 Define feature dataset envelope with feature timestamp and label timestamp.
- [x] 6.2 Define initial supervised labels from governed decisions and later outcomes.
- [x] 6.3 Add leakage checks for point-in-time feature generation.
- [x] 6.4 Add lineage from feature rows to historical events and snapshots.
- [x] 6.5 Produce a first offline feature dataset for validation, not model training.

## 7. Verification and observability

- [ ] 7.1 Test point-in-time reconstruction against known workflow fixtures.
- [ ] 7.2 Test current-vs-historical comparisons.
- [ ] 7.3 Test warehouse export manifest integrity.
- [ ] 7.4 Test retention and deletion behavior.
- [ ] 7.5 Add metrics for event write volume, snapshot freshness, export lag, and failed retrospective jobs.
