# ADR-006: Retrospective Intelligence as an Internal Bounded Context

## Status

Accepted

## Date

2026-07-11

## Context

UKIP accumulates operational knowledge through imports, enrichment, authority
resolution, normalization, governance reviews, metric computation, and user
decisions. Today that history survives mainly as current state plus scattered
audit evidence (`audit_logs`, `data_lifecycle_events`, `author_merge_audits`,
`enrichment_scheduler_runs`, per-metric backfill notes). There is no governed way
to reconstruct *what UKIP knew at a point in time*, to explain *how a value
changed*, or to prepare historical data for analytical warehouses and future
machine-learning workflows.

We need a retrospective analytical capability, but the operational PostgreSQL
schema is optimized for current-state platform behavior. Retrospective analysis
has different access patterns: append-only history, time-windowed reads, trend
and cohort analysis, drift detection, backtesting, and ML dataset generation.
Mixing those workloads into the operational tables risks performance regressions
and couples analytical needs to operational migrations.

At the same time, extracting a separate analytics microservice now would be
premature: we have no measured scaling pressure, no separate team ownership, and
no warehouse commitment. Deployment simplicity is currently a feature.

## Decision

Build the **retrospective intelligence layer** as an **internal bounded context
first**, with explicit contracts (historical events, snapshots, warehouse export,
ML feature generation) that do **not** assume co-location with operational tables.
Defer both warehouse deployment and microservice extraction.

Ordering of commitments:

1. **Internal bounded context first.** Historical events and snapshots are
   append-only, tenant-scoped, schema-versioned, and provenance-linked. They may
   live in the existing PostgreSQL database (dedicated tables / analytical schema)
   or later in DuckDB — the writer and query contracts must not depend on which.
2. **Warehouse-ready export second.** Export contracts target BigQuery-compatible
   schemas (partition/clustering columns, versioned manifests, tenant isolation)
   but the layer MUST operate with no warehouse configured, reporting
   `not_configured` on export readiness.
3. **Microservice extraction later**, only when the extraction criteria below are
   met — not on speculation.

Cross-cutting rules that this ADR ratifies (detailed in the source inventory &
governance doc):

- Retrospective reads are **read-only** with respect to operational entity,
  enrichment, authority, and journal-metric tables.
- Every historical record carries `org_id`, `schema_version`, `recorded_at`, and
  a stable domain identifier, and preserves null/provenance semantics
  (source-provided vs inferred vs normalized vs unknown vs unavailable).
- Historical payloads are **bounded** and MUST NOT store reusable credentials or
  raw provider secrets.
- Append-only except for **governed retention deletion**, reusing the EPIC-016
  `RetentionPolicy` / `DataLifecycleEvent` machinery rather than inventing a
  parallel deletion path.

### Extraction criteria

Extract the bounded context into a separately deployed service when **at least
two** of the following are true:

- retrospective queries materially affect operational database performance;
- historical data volume requires a warehouse-first execution model;
- ML training or feature generation needs independent scaling;
- another system needs the retrospective API as a productized interface;
- separate team ownership or release cadence becomes necessary;
- regulatory retention, deletion, or audit controls diverge from the core app;
- event ingestion volume requires independent worker capacity.

### Extraction-criteria review cadence

- **Quarterly** review of the extraction criteria as a standing agenda item in
  the enterprise-architecture governance review, starting the first full quarter
  after the first retrospective events ship to production.
- **Event-triggered** review out of cadence whenever any single criterion is
  observed to be met in production (e.g., a retrospective query appears in slow-
  query monitoring, or event ingestion saturates a worker).
- Each review records a dated decision — *stay internal* or *begin extraction* —
  with the criteria evidence, appended to this ADR's References or a linked
  governance log. Staying internal is the default and requires no action.

## Consequences

- **Easier:** point-in-time reconstruction, current-vs-prior comparison, and
  warehouse/ML readiness without touching operational hot paths; a clean seam to
  extract later behind stable contracts; reuse of existing tenant-isolation and
  retention governance.
- **Harder:** operational workflows must emit governed retrospective events at
  their decision points (extra write path); two representations of some data
  (current state + historical facts) must be kept semantically consistent; schema
  versioning discipline becomes mandatory from day one because history cannot be
  retroactively re-shaped.

## References

- Change: `retrospective-intelligence-layer` (proposal.md, design.md)
- Specs: `retrospective-intelligence-layer`,
  `historical-warehouse-export-contract`, `ml-feature-readiness-contract`
- Companion: `docs/architecture/retrospective-intelligence-source-inventory.md`
  (source workflow inventory; tenant/retention/audit rules; schema versioning &
  payload-size limits)
- Prior art: ADR-001 (provenance layering), ADR-002 (canonical governance),
  EPIC-016 (`RetentionPolicy`, `DataLifecycleEvent`), EPIC-012 (tenant isolation)
