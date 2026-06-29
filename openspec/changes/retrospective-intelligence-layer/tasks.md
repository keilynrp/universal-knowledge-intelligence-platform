## 1. Architecture and governance

- [ ] 1.1 Record an ADR for internal bounded context first, warehouse-ready export second, microservice extraction later.
- [ ] 1.2 Inventory source workflows that create retrospective value: import, enrichment, journal metrics, authority, NIL, provenance, governance review, and user decisions.
- [ ] 1.3 Define tenant, retention, deletion, and audit rules for historical records.
- [ ] 1.4 Define schema versioning and payload-size limits.
- [ ] 1.5 Define extraction criteria review cadence.

## 2. Historical contracts

- [ ] 2.1 Add historical event envelope.
- [ ] 2.2 Add snapshot envelope.
- [ ] 2.3 Add event-family registry and schema-version registry.
- [ ] 2.4 Add idempotency keys for scheduled snapshots and replayed writers.
- [ ] 2.5 Add tests for tenant scoping, append-only writes, and schema-version validation.

## 3. Initial retrospective data

- [ ] 3.1 Emit journal metric computed and recomputed events.
- [ ] 3.2 Emit enrichment lifecycle events.
- [ ] 3.3 Emit authority and NIL decision events.
- [ ] 3.4 Materialize journal metric, enrichment coverage, and authority readiness snapshots.
- [ ] 3.5 Backfill bounded historical events where trustworthy source timestamps exist.

## 4. Retrospective query and UI

- [ ] 4.1 Add point-in-time lookup service.
- [ ] 4.2 Add current-vs-snapshot comparison service.
- [ ] 4.3 Add cohort and metric time-series helpers.
- [ ] 4.4 Add minimal dashboard for historical comparison.
- [ ] 4.5 Add provenance explanations for retrospective values.

## 5. Warehouse export

- [ ] 5.1 Define BigQuery-compatible table schemas and partitioning.
- [ ] 5.2 Add export manifest format with dataset version, tenant scope, row counts, and schema version.
- [ ] 5.3 Add idempotent export job for historical events.
- [ ] 5.4 Add idempotent export job for snapshots and analytical marts.
- [ ] 5.5 Add export validation for row counts, schema drift, and tenant isolation.

## 6. ML readiness

- [ ] 6.1 Define feature dataset envelope with feature timestamp and label timestamp.
- [ ] 6.2 Define initial supervised labels from governed decisions and later outcomes.
- [ ] 6.3 Add leakage checks for point-in-time feature generation.
- [ ] 6.4 Add lineage from feature rows to historical events and snapshots.
- [ ] 6.5 Produce a first offline feature dataset for validation, not model training.

## 7. Verification and observability

- [ ] 7.1 Test point-in-time reconstruction against known workflow fixtures.
- [ ] 7.2 Test current-vs-historical comparisons.
- [ ] 7.3 Test warehouse export manifest integrity.
- [ ] 7.4 Test retention and deletion behavior.
- [ ] 7.5 Add metrics for event write volume, snapshot freshness, export lag, and failed retrospective jobs.
