## Why

UKIP accumulates operational knowledge through imports, enrichment, authority
resolution, normalization, governance reviews, metric computation, and user
decisions. Today that history is useful mainly as current state plus audit
evidence. The platform needs a governed retrospective layer that can reconstruct
what UKIP knew at a point in time, explain how it changed, and prepare historical
data for analytical warehouses and future machine-learning workflows.

This capability should be separated architecturally from the operational core
without prematurely extracting a microservice. UKIP needs a bounded analytical
context now, with clean contracts that allow later export to BigQuery or another
warehouse and eventual extraction into an independently scalable service.

## What Changes

- Define a retrospective intelligence bounded context inside UKIP.
- Introduce append-only historical events and time-versioned snapshots.
- Preserve tenant scope, provenance, source authority, schema versioning, and
  reproducible point-in-time reads.
- Establish a warehouse export contract suitable for BigQuery or equivalent
  analytical stores.
- Establish ML feature-readiness requirements for future neural-network and
  statistical-learning workflows.
- Define criteria for when the bounded context should be extracted into a
  separate service.

## Non-goals

- Immediate BigQuery deployment.
- Immediate neural-network training or model-serving infrastructure.
- Replacing the operational PostgreSQL schema.
- Capturing every low-level database mutation as a historical fact.
- Guaranteeing exactly-once event delivery.
- Building a separate microservice in the first implementation phase.

## Capabilities

### New

- `retrospective-intelligence-layer`
- `historical-warehouse-export-contract`
- `ml-feature-readiness-contract`

### Modified

- entity provenance and audit patterns
- enrichment metrics and scheduler evidence
- journal metrics and bibliometric analytics
- authority readiness and NIL review workflows
- enterprise architecture governance

## Success Criteria

- UKIP can answer point-in-time questions about selected entities, metrics, and
  derived signals.
- Historical records are append-only, tenant-scoped, schema-versioned, and tied
  to provenance.
- Retrospective reads do not depend on mutating operational tables.
- Historical analysis can compare current state against a prior snapshot.
- Export jobs can produce bounded, versioned warehouse datasets without
  leaking credentials or cross-tenant data.
- ML-ready datasets can be generated with feature timestamps, labels, lineage,
  and leakage controls.
- The context can later be extracted behind the same contracts when workload,
  team ownership, or scaling pressure justifies it.
