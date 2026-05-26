## Context

Affiliation is one of the canonical institutional anchors in UKIP's research-stakeholder graph: it links a publication to the institutions whose researchers produced it, drives geographic analytics, and feeds authority resolution against ROR. A wrong scalar value in `attrs.affiliation` does not crash anything — it silently degrades every downstream metric that branches on institutional identity (heatmaps, co-authorship networks, country-of-origin distributions, ROR confirmation rate).

The bug went undetected for 2.5 months because:

- The structured affiliation layer (`canonical_affiliations`, `author_affiliations`) was introduced in `19e97ff` *together with* the fix-forward. New entities imported after that date had both the scalar and structured layers, and any UI/analytics that consumed the structured layer worked correctly.
- The corpus was small enough (547 entities) that the wrong scalar value rendered in occasional spot-checks as a journal name, but no one had a "weird affiliation values" alert wired.
- Re-enrichment never repaired the legacy entries because the cascade fell to Crossref (no affiliations) due to a separate, older bug in `OpenAlexAdapter`.

## Goals

- Document the root cause of all three bug layers so future engineers reading this change understand the failure mode in full.
- Formalize the invariants that, if they had existed as tests, would have prevented each layer.
- Quantify the operational outcome of the remediation so governance reviewers have evidence the fix worked.
- Identify systemic gaps in our review process that allowed three independent bugs to compound without detection.

## Non-Goals

- Refactor the enrichment cascade architecture. The cascade design is fine; the bug was in the adapter contract.
- Migrate the affiliation column out of `attributes_json` into a dedicated relational table. Out of scope for this incident.
- Backfill historical preprints that genuinely have no institution metadata in OpenAlex. Honest nulls > fabricated data.

## Decisions

### D1 — Root cause is "contract gap", not "code defect"

Each bug layer is technically a small mistake (one assignment, one missing property, one false-positive comparison). The deeper failure mode is that **none of the touched code paths had a contract test**. Tests that would have caught each layer:

- `cbe3255`: a test asserting `attrs.affiliation` is only ever derived from `rec.affiliations`, never from `rec.publisher`.
- `OpenAlexAdapter` is_active: a test that iterates every concrete `BaseScientometricAdapter` and asserts `is_active` is declared.
- Backfill clobber: a test that seeds an entity with both the joined affiliation string AND `canonical_affiliations`, then asserts the migration does not clear it.

All three tests now exist (see `test_api_import_affiliation_contract.py`, `test_enrichment_adapter_contract.py`). The decision is to treat contract tests as a **first-class deliverable** for any code that writes into `attributes_json` or participates in the enrichment cascade.

### D2 — `is_active` defaulting to False on missing attribute is preserved (not switched to True)

The natural reaction is "change `getattr(adapter, 'is_active', False)` to default `True` so a forgotten property doesn't take down a provider." Rejected for two reasons:

1. The cascade enables providers that may require credentials (Scopus, WoS). Defaulting to active would silently call out to providers that aren't configured, risking 401/403 storms.
2. The contract test now makes the missing-attribute case impossible to merge. Defending in depth would replace one bug with a different one.

The cascade keeps fail-closed semantics; the test prevents the omission.

### D3 — Backfill uses presence of structured layer as proof of modern provenance

`fix_legacy_affiliations.py` short-circuits when `canonical_affiliations` or `author_affiliations` carry any entries. The reasoning is causal: the bug-era code path (cbe3255) **never wrote those layers**. Their presence is a stronger signal of modern provenance than any string comparison could provide. The previous fuzzy-name-match approach was a proxy for the same idea but failed on the joined display format.

This decision is intentionally exclusive — it does not check the structured layer for "real" content. Even an empty placeholder dict would trigger the short-circuit. That's the right behavior: the bug-era code never wrote *any* form of structured layer, so any non-empty container is proof.

### D4 — Backups under `attrs._legacy_affiliation_backup` are permanent

The migration moves the cleared value into a backup key rather than deleting it. This costs ~80 bytes per row but provides:

- Forensic auditability — the original wrong value is recoverable.
- Reversibility — operators can restore any affected entity from the backup if needed.
- Evidence — the backup itself serves as the marker that an entity was touched by the migration.

The backup key is not exposed by any read endpoint and is invisible to users. It stays in the database indefinitely as part of the incident ledger.

### D5 — Frontend dedup group `affiliation` is empty, not removed

`EntityTableDetailsModal.displayedValuesByGroup.affiliation` is now `[]` rather than removed. Keeping the empty key documents that the affiliation group exists in the modal's mental model but has no primary slot, so the dedup pass has nothing to compare against. Future maintainers seeing the empty array will read the comment block above it and not reintroduce the buggy values.

## Three-Layer Bug Cascade

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Layer 1 — Import (cbe3255 → 19e97ff)                                     │
│ ─────────────────────────────────────                                    │
│ /import/openalex called.                                                 │
│ OpenAlex returns: primary_location.source.display_name = "Journal of X"  │
│ Adapter sets: rec.publisher = "Journal of X"                             │
│ Bug: _ingest_records writes attrs["affiliation"] = rec.publisher.        │
│ Window: 2026-05-13 to 2026-05-20 (one week).                             │
│ Persistence: indefinite (data sits in DB after the code is fixed).       │
└────┬─────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Layer 2 — Enrichment Cascade (since OpenAlex adapter inception)          │
│ ──────────────────────────────────────────────────────────────────────── │
│ Worker dispatches re-enrichment.                                         │
│ Reads cascade order from env / default.                                  │
│ For each provider: skip if not getattr(adapter, 'is_active', False).     │
│ OpenAlexAdapter has no is_active property → silently skipped.            │
│ Falls to Crossref. Crossref doesn't return affiliations.                 │
│ Worker writes nothing into attrs.affiliation. Entity stays wrong.        │
│ Window: since the adapter was added (~3 months).                         │
│ Persistence: every re-enrichment attempt is a no-op for affiliations.    │
└────┬─────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ Layer 3 — Migration Race (initial fix_legacy_affiliations)               │
│ ──────────────────────────────────────────────────────────────────────── │
│ After Layer 2 fix deployed, worker re-enriches.                          │
│ OpenAlex returns institutions. Worker writes:                            │
│   attrs.affiliation = "Stockholm Univ, SE; Columbia Univ, US" (joined)   │
│   attrs.canonical_affiliations = [{name: "Stockholm Univ", ...}, ...]    │
│ Operator re-runs migration.                                              │
│ Script: normalize_name(joined_string) != normalize_name(canonical_name). │
│ → flagged as residue → cleared + backed up.                              │
│ Worker re-pops it from pending → fixes it again.                         │
│ Visible churn: fixed=44 on second run, no permanent loss but unstable.   │
└──────────────────────────────────────────────────────────────────────────┘
```

## Preventive Controls

| Control | Type | Location | Catches |
|---|---|---|---|
| Auto-discovery `is_active` contract test | pytest parametrized | `backend/tests/test_enrichment_adapter_contract.py` | Any new adapter that forgets `is_active` |
| OpenAlex-specific `is_active` pin | pytest | same file | Refactor that gates OpenAlex behind a credential check |
| `_ingest_records` publisher-leak guard | pytest | `backend/tests/test_api_import_affiliation_contract.py` | Any reintroduction of `attrs.affiliation = rec.publisher` |
| `_ingest_records` happy-path contract | pytest | same file | Regressions on the `rec.affiliations` → `attrs.affiliation` mapping |
| Migration anti-clobber on canonical_affiliations | pytest | same file | Migration script clearing modern data |
| Migration anti-clobber on author_affiliations | pytest | same file | Symmetric to above |
| Migration idempotency | pytest | same file | A second `--dry-run` returning `fixed > 0` after an apply |
| RBAC + payload validation on admin endpoint | pytest | `backend/tests/test_admin_data_fixes.py` | Unauthorized or malformed migration triggers |

## Lessons

1. **Contract tests for write paths into `attributes_json`** must be a default deliverable. The bug surface area of "key/value with no schema" is enormous; only contract tests can constrain it.
2. **`getattr(obj, attr, default)` is a foot-gun** when the default has semantic weight. The cascade should have either failed loudly on missing attributes (preferred for safety-critical iteration) or had a discovery test.
3. **Re-running operator scripts immediately after deploys** is an anti-pattern when the deploy could change behavior the script depends on. The Layer 3 race was a manifestation of "operator and worker concurrent on the same rows." The script now self-defends, but ideally operator scripts should pause the worker or hold a row-level lock.
4. **Linked-data layers should be the source of truth, not the joined display string**. The frontend should prefer `canonical_affiliations[].name` over `attrs.affiliation` for institution lookups; the scalar is for backward-compat display only. Not in this change's scope but flagged as a follow-up.
5. **Honest nulls are better than fabricated data**. The 56 entities without affiliation (13% of the batch) reflect what OpenAlex actually knows about those papers. The platform's job is to surface that truth, not to invent it.

## Open Questions

- Should we add a periodic audit job that scans for `attrs.affiliation` values that don't match any `canonical_affiliations[].name`? Useful as a continuous integrity check, but risks alert fatigue. Defer to a follow-up change.
- Should `_legacy_affiliation_backup` ever be cleaned up? Storage cost is negligible (~30 KB total across 437 entities). Recommend leaving it indefinitely until a future privacy/retention review.
- Should the frontend prefer `canonical_affiliations` over `attrs.affiliation` for display? Out of scope here; tracked separately.

## Rollback

If the remediation needs to be reverted:

1. Restore the `attrs.affiliation` value from `attrs._legacy_affiliation_backup` for each affected entity (script provided in the migration docstring).
2. Set `enrichment_status` back to `completed` on those rows.
3. Revert the `is_active` property on `OpenAlexAdapter` (commit `22d0d84`) — the cascade will return to its prior state of silently skipping OpenAlex.

Rollback is reversible; nothing in this change deletes data without backup.
