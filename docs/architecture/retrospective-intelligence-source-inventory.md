# Retrospective Intelligence — Source Workflow Inventory & Governance

> Companion to [ADR-006](../adr/006-retrospective-intelligence-bounded-context.md)
> and the `retrospective-intelligence-layer` change. Satisfies Phase 1 tasks
> 1.2 (source inventory), 1.3 (tenant/retention/deletion/audit rules), and
> 1.4 (schema versioning & payload-size limits).

## 1. Source workflow inventory (task 1.2)

Workflows in the operational core that create retrospective value. Each row is a
candidate emission point for the historical event/snapshot writers. "Current
truth today" names where the state lives now; "retrospective gap" is what is lost
once that state is overwritten.

| # | Workflow | Operational source (models / services) | Retrospective value | Current truth today | Retrospective gap |
|---|----------|------------------------------------------|---------------------|---------------------|-------------------|
| 1 | **Entity import** | `ImportBatch`, `ScheduledImport`, `UniversalEntity` | volume, source mix, and shape of what entered over time | latest entity rows | prior import composition; re-imports overwrite |
| 2 | **Normalization / harmonization** | `NormalizationRule`, `HarmonizationLog`, `HarmonizationChangeRecord` | how a value was transformed and when rules changed | change records (partial) | pre-normalization values after cleanup/purge |
| 3 | **Entity merge / split / promote** | `AuthorMergeSuggestion`, `AuthorMergeAudit`, canonical promotion | identity lineage over time | merge audit (authors only) | non-author entity merge history |
| 4 | **Enrichment lifecycle** | `EnrichmentSchedulerRun`, `DomainEnrichmentPolicy`, `SourceProfile` | requested/completed/failed/retried/refreshed coverage | latest run + entity attributes | per-attempt outcome history; coverage drift |
| 5 | **Authority resolution** | `AuthorityRecord`, `AuthorityResolveJob`, `ResolutionThreshold`, `AuthorityScoringFeedback` | candidate created/accepted/rejected decisions | current record status | decision timeline; threshold changes |
| 6 | **NIL review** | `AuthorityRecord` (NIL state), review queue | "not in list" determinations by reviewer | current NIL flag | when/why NIL was set; reversals |
| 7 | **Journal metric computation** | `JournalMetric` (`two_yr_mean_citedness`, NIF, `nif_bayes`) | computed / recomputed / backfilled metric values | one row per ISSN-L | prior metric values before recompute/backfill |
| 8 | **Source health / provider coverage** | `SourceProfile`, `AlertChannel`, circuit breaker (ADR-004) | provider availability and coverage changes | current profile | coverage/health timeline |
| 9 | **Governance review decisions** | `MappingSuggestionRecord`, GenAI governance (ADR-005) | human accept/reject with evidence | current suggestion status | decision provenance over time |
| 10 | **User / system decisions** | `AuditLog`, `DataLifecycleEvent`, workflow runs | actor + role + tenant-safe context for actions | audit rows (HTTP-level) | domain-semantic decision events |

### Initial emission priority

Per the change's rollout path, the **first** writers cover a narrow, high-value
slice (design.md "Initial event families" / Phase 3 tasks):

1. Journal metric **computed** and **recomputed** events (#7).
2. Enrichment **lifecycle** events (#4).
3. Authority and **NIL decision** events (#5, #6).

Snapshots materialized first: **journal metric**, **enrichment coverage**, and
**authority readiness** (Phase 3.4). Everything else in the table is deferred
until these prove the contracts in production.

## 2. Tenant, retention, deletion & audit rules (task 1.3)

### Tenant scope

- Every historical event and snapshot carries `org_id`, resolved from the caller
  at write time — never inferred later from mutable operational joins. This
  follows EPIC-012 tenant isolation (`org_id` nullable; `NULL` = platform-level).
- `org_id = NULL` is reserved for **governed platform-level aggregates** with no
  tenant-identifiable payload. Customer-scoped history MUST carry a concrete
  `org_id`.
- Retrospective readers return a record only to authorized users within its
  `org_id` scope. Cross-tenant reads are impossible through the query service.

### Retention & deletion

- Historical records are **append-only** except for governed retention deletion.
- Reuse EPIC-016 machinery rather than a parallel path:
  - `RetentionPolicy` gains retrospective `data_class` values —
    `retrospective_events` and `retrospective_snapshots` — so per-org (or
    platform-default `org_id = NULL`) windows apply. `retention_days = NULL`
    means no auto-purge.
  - Every purge or right-to-erasure over historical records emits a
    `DataLifecycleEvent` (`action = purge | deletion`) with per-store evidence
    counts, so deletions are themselves auditable.
- Deletion is the **only** permitted mutation of a stored historical payload.
  Application code attempting any other update MUST be rejected (enforced in the
  writer + tested in task 2.5 / 7.4).

### Audit

- Retrospective **writes** are evidence, not user-facing mutations; they do not
  need a second `AuditLog` row per event (that would double-count). Retrospective
  **administrative actions** (manual backfill, export trigger, retention purge)
  DO record an `AuditLog` / `DataLifecycleEvent` entry with actor and role.
- Each historical event stores `actor_type`, `actor_id`, and `correlation_id`
  so a decision can be traced to the workflow and principal that produced it,
  without embedding PII beyond what the operational audit trail already holds.

## 3. Schema versioning & payload-size limits (task 1.4)

### Schema versioning

- Every event and snapshot row carries an integer/string `schema_version`
  scoped to its `event_type` / `snapshot_type` (an event-family registry, task
  2.3, owns the current version per family).
- History is **immutable**: a schema change is a **new version**, never an
  in-place rewrite of existing rows. Readers dispatch on `schema_version` and
  MUST tolerate multiple versions of the same family coexisting.
- Additive changes (new optional field) bump the family version; removals or
  meaning changes require a new version and a migration note in the registry.
- Export schemas (`historical-warehouse-export-contract`) carry the same
  `schema_version` so warehouse consumers can detect drift.

### Payload-size limits

- Historical payloads are **bounded summaries of a decision**, not full document
  dumps. Initial hard limit: **32 KB** serialized JSON per event/snapshot
  payload. Writers reject oversized payloads rather than truncating silently.
- Large source artifacts are referenced by lineage id (event id, snapshot id,
  source entity version, or object reference), never inlined.
- Payloads MUST NOT contain reusable credentials, raw provider secrets, or full
  raw provider responses — only governed, tenant-safe fields.

## 4. Open items carried into later phases

- **Storage placement** (PostgreSQL analytical schema vs DuckDB) is deliberately
  left to Phase 2 implementation; contracts are written to not depend on it
  (ADR-006).
- Concrete envelope column definitions land in Phase 2 (tasks 2.1–2.2).
- The event-family & schema-version **registry** is Phase 2 (task 2.3); this doc
  fixes the *rules* it must enforce.
