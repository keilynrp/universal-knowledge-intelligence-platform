## Governance

This change is subordinate to [`canonical-semantic-data-governance`](../../changes/archive/2026-05-23-canonical-semantic-data-governance/proposal.md) and operates as a `canonical-specialization` retrospective. It documents a corpus-wide data integrity incident on the `affiliation` field, the three-layer root cause, the remediation applied, and the preventive controls now in place. It does not introduce new capabilities; it formalizes invariants that should have been guarded from day one.

## Why

Between 2026-05-13 and 2026-05-20 the production import pipeline silently stored journal/publisher names under `attributes_json.affiliation` instead of the institutional affiliations OpenAlex returned. The incident surfaced on 2026-05-25 when a stakeholder noticed entity 25177 ("Open Science Framework (OSF)") rendering "Journal of the Medical Library Association JMLA" in the affiliation card.

Investigation uncovered **three independent bugs in cascade** that together prevented the platform from ever surfacing institutional affiliations from OpenAlex via the cascade:

1. **`cbe3255` data leak** — `_ingest_records` in `backend/routers/api_import.py` mapped `rec.publisher` into `attrs["affiliation"]`. The OpenAlex adapter populates `EnrichedRecord.publisher` from `primary_location.source.display_name`, which is the journal name, not the publisher. The bug existed for one week (fixed in `19e97ff`) but its data footprint persisted in production until the 2026-05-25 backfill.
2. **`OpenAlexAdapter.is_active` undeclared** — the enrichment cascade in `backend/enrichment_worker.py` reads `getattr(adapter, 'is_active', False)` for activation. OpenAlex shipped without that property since its inception. The cascade silently treated OpenAlex as inactive and always fell to Crossref (no affiliations) or PubMed for re-enrichment. Direct `/import/openalex` calls bypass the cascade and were unaffected — which is why the incident hid behind apparent partial coverage.
3. **Backfill script race on display-string format** — the first iteration of `backend/scripts/fix_legacy_affiliations.py` compared the joined OpenAlex display string (`"Stockholm University, SE; Columbia University, US"`) against `canonical_affiliations[].name` (bare `"Stockholm University"`). The mismatch falsely flagged newly-repopulated rows as legacy residue and cleared them. The worker re-populated them transparently in the same loop, so no permanent loss occurred, but the next operator run would have repeated the clobber.

Each layer in isolation was survivable. Combined, they produced a corpus where 80%+ of OpenAlex-imported entities carried wrong scalar affiliation, no structured affiliation layer (the bug-era code predated those fields), and no mechanism to repair via re-enrichment because the adapter was invisible to the cascade.

## What Changes

- **New**: Formal contract on `_ingest_records` — `rec.publisher` MUST NOT be written into `attrs.affiliation`. Enforced by `backend/tests/test_api_import_affiliation_contract.py`.
- **New**: Formal contract on every `BaseScientometricAdapter` subclass — MUST declare `is_active` returning `bool`. Enforced by auto-discovery in `backend/tests/test_enrichment_adapter_contract.py`.
- **New**: `OpenAlexAdapter.is_active` property (returns `True`; polite-pool via mailto, no API key required).
- **New**: `ScholarAdapter.is_active` property (returns `True` only when proxy is configured; matches existing warning behavior).
- **New**: `backend/scripts/fix_legacy_affiliations.py` — idempotent migration with `--dry-run` / `--requeue-enrichment` / `--org-id` / `--limit`. Backups every cleared value under `attrs._legacy_affiliation_backup`.
- **New**: `POST /admin/data-fixes/legacy-affiliations` — super_admin endpoint wrapping the migration, audit-logged.
- **Modified**: `backend/scripts/fix_legacy_affiliations.py` short-circuits when `canonical_affiliations` or `author_affiliations` has any entries. Their presence proves the data came from the modern code path and must not be treated as residue.
- **Modified**: `frontend/app/components/EntityTableDetailsModal.tsx` — `displayedValuesByGroup.affiliation` no longer contains journal/venue/publisher fields. Genuine affiliations no longer hide behind false-positive deduplication.
- **Removed**: `.github/workflows/fix-legacy-affiliations.yml` — incompatible with the Dokploy deployment model (Postgres on internal Docker network, not exposed to GitHub runners). The admin endpoint + Dokploy shell cover the same use cases without exposing infrastructure.

## Capabilities

This change does not introduce capabilities. It retroactively constrains the following existing ones:

### Modified Capabilities

- `enrichment-cascade`: every concrete provider adapter must declare `is_active`. Missing the attribute is treated as a contract violation, not a default-inactive fallback.
- `scientific-import-api`: `_ingest_records` cannot mirror `rec.publisher` into `attrs.affiliation`. Publisher belongs to `attrs.publisher`. Affiliations come from `rec.affiliations` (joined display) and `rec.canonical_affiliations` / `rec.author_affiliations` (structured).
- `data-repair-operations`: legacy backfill scripts must skip rows where the structured canonical/author affiliation layers carry data. Their presence is proof of modern provenance.
- `entity-detail-presentation`: deduplication groups must not cross-reference fields from different semantic groups (journal/venue ≠ affiliation).

## Outcome

**Corpus impact (2026-05-25 production backfill):**

| Metric | Before | After |
|---|---|---|
| Entities in affected batch | 437 | 437 |
| `canonical_affiliations` populated | 0 (0%) | 350 (80%) |
| `author_affiliations` populated | 0 (0%) | 381 (87%) |
| Wrong scalar `affiliation` (journal as institution) | 437 | 0 |
| Backups preserved in `_legacy_affiliation_backup` | n/a | 437 (reversible) |
| Residue without affiliation (acceptable null) | 437 | 56 (13%) — includes 11 genuine preprints |

**Test coverage added:**

| Suite | Tests | Purpose |
|---|---|---|
| `test_enrichment_adapter_contract.py` | 17 | Auto-discovers every concrete adapter, asserts `is_active` is declared and returns `bool`. Plus OpenAlex-specific pin. |
| `test_api_import_affiliation_contract.py` | 11 | 3 invariants on `_ingest_records`, 8 invariants on the migration script (incl. 2 anti-clobber tests reproducing the production race). |
| `test_admin_data_fixes.py` | 11 | RBAC + payload validation + behavior on the admin endpoint. |

Total: **39 new regression tests**, all green across the affiliation suite.

## References

- Root-cause commits: `cbe3255` (introduction), `19e97ff` (fix-forward), `22d0d84` (adapter contract), `ede438e` (script race), `a4846f7` (frontend dedup).
- Operationally-affected entity sample: 25177, 25391, 25520, 25565, 25588, 25609.
- Governance parent: `canonical-semantic-data-governance` § "Authority and enrichment boundaries" — this incident materialized the contract that section already defined in prose.
