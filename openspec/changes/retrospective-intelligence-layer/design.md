## Context

UKIP's operational database is optimized for current platform behavior:
catalogs, entity resolution, enrichment workflows, authority decisions, metrics,
and user-facing analytics. Retrospective analysis has different needs:
append-only history, time-windowed reads, trend analysis, cohort comparison,
backtesting, data-quality drift, and machine-learning dataset generation.

The design separates these concerns as a bounded context while preserving the
current deployment simplicity of the application.

## Architecture decision

Build the retrospective intelligence layer as an internal bounded context first,
with explicit contracts for historical events, snapshots, warehouse export, and
ML feature generation. Do not extract a microservice until at least one of the
accepted extraction criteria is met.

The initial implementation may store historical tables in the existing database
or a separate analytical schema. The API and writer contracts must not assume
co-location with operational tables.

## Components

1. **Historical event writer:** accepts governed domain events from operational
   workflows and persists append-only records.
2. **Snapshot writer:** materializes point-in-time entity, metric, and signal
   snapshots on a schedule or after accepted workflow milestones.
3. **Retrospective query service:** reads historical events and snapshots
   without mutating operational state.
4. **Analytical mart builder:** derives time-series, cohorts, drift summaries,
   and backtesting tables from historical facts.
5. **Warehouse exporter:** emits versioned, tenant-scoped datasets for BigQuery
   or an equivalent warehouse.
6. **Feature dataset builder:** creates ML-ready training and evaluation
   datasets with feature timestamps, labels, and lineage.

## Data model principles

- Historical records are append-only except for governed retention deletion.
- Every record carries `org_id`, `schema_version`, `recorded_at`, and a stable
  domain identifier.
- Derived records include lineage to source events, snapshot IDs, or source
  entity versions.
- Point-in-time queries use event/snapshot timestamps, never current mutable
  fields as implicit truth.
- Unknown, null, inferred, and source-provided values retain distinct semantics.
- Historical payloads must be bounded and must not store reusable credentials.

## Initial event families

- entity imported, normalized, merged, split, and promoted;
- enrichment requested, completed, failed, retried, and refreshed;
- authority candidate created, accepted, rejected, and marked NIL;
- journal metric computed, recomputed, and backfilled;
- source health and provider coverage changed;
- governance review decision recorded;
- user or system decision emitted with actor, role, and tenant-safe context.

## Initial snapshot families

- entity snapshot;
- relationship snapshot;
- metric snapshot;
- journal metric snapshot;
- authority readiness snapshot;
- enrichment coverage snapshot;
- data-quality snapshot;
- source coverage snapshot.

## Warehouse posture

BigQuery or a similar warehouse is the preferred future execution plane for
large retrospective analytics, BI, and ML feature engineering. The initial UKIP
implementation should not require it, but it must export data using stable
schemas, partition columns, lineage columns, and tenant-safe access boundaries.

## ML posture

The retrospective layer should prepare data for future neural-network and
statistical-learning workflows by generating reproducible feature datasets. It
does not train models initially. Feature generation must prevent time leakage by
ensuring every feature was available before the prediction or label timestamp.

## Extraction criteria

Extract the bounded context into a separately deployed service when at least two
of the following are true:

- retrospective queries materially affect operational database performance;
- historical data volume requires a warehouse-first execution model;
- ML training or feature generation needs independent scaling;
- another system needs the retrospective API as a productized interface;
- separate team ownership or release cadence becomes necessary;
- regulatory retention, deletion, or audit controls diverge from the core app;
- event ingestion volume requires independent worker capacity.

## Rollout path

1. Add contracts and schemas.
2. Write a narrow set of journal, enrichment, and authority events.
3. Materialize daily snapshots for selected metrics.
4. Add retrospective query APIs and a minimal historical comparison dashboard.
5. Add export jobs behind feature flags.
6. Add ML-ready dataset generation once labels and decisions are governed.
7. Re-evaluate extraction criteria after production observation.
