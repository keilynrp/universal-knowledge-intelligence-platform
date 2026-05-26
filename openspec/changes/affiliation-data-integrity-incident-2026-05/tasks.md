## 1. Root cause analysis

- [x] 1.1 Reproduce the incident on a sample production entity (25177) and identify the wrong scalar value in `attrs.affiliation`.
- [x] 1.2 Trace the value back to `cbe3255` and confirm `19e97ff` fixed the code path but not the data.
- [x] 1.3 Identify why re-enrichment did not repair the data (OpenAlex inactive in cascade).
- [x] 1.4 Identify the third bug (migration script false positive) before it caused permanent data loss in production.

## 2. Backfill script

- [x] 2.1 Implement `backend/scripts/fix_legacy_affiliations.py` with `--dry-run`, `--requeue-enrichment`, `--org-id`, `--limit`.
- [x] 2.2 Implement defensive backup under `attrs._legacy_affiliation_backup`.
- [x] 2.3 Restrict to affected sources (`openalex`, `pubmed`, `crossref`) to avoid touching unrelated rows.
- [x] 2.4 Make idempotent (re-runs after a successful apply return `fixed=0`).
- [x] 2.5 Short-circuit when `canonical_affiliations` or `author_affiliations` carry entries (race-condition guard).
- [x] 2.6 Add regression tests for the migration contract (8 tests).

## 3. Adapter contract

- [x] 3.1 Declare `OpenAlexAdapter.is_active` (returns `True`; no API key required).
- [x] 3.2 Declare `ScholarAdapter.is_active` (returns `True` only when proxy is configured).
- [x] 3.3 Add `test_enrichment_adapter_contract.py` that auto-discovers every concrete `BaseScientometricAdapter` subclass and asserts `is_active` returns a `bool`.
- [x] 3.4 Add OpenAlex-specific pin asserting `is_active is True` (regression guard against credential-gating refactors).

## 4. Ingest contract

- [x] 4.1 Add `test_api_import_affiliation_contract.py` covering: publisher never leaks into affiliation; real affiliations populate both `attrs.affiliation` and `attrs.affiliations`; empty case stays clean.
- [x] 4.2 Add anti-clobber tests reproducing the production race observed on entities 25609 / 25261 / 25364 / 25435 / 25509.

## 5. Admin endpoint

- [x] 5.1 Implement `POST /admin/data-fixes/legacy-affiliations` wrapping the migration with safe defaults (`dry_run=True`).
- [x] 5.2 Restrict to `require_role("super_admin")`.
- [x] 5.3 Reject unknown fields and enforce positive `org_id` / `limit` constraints.
- [x] 5.4 Add 11 endpoint tests covering RBAC, payload validation, and behavior.
- [x] 5.5 Wire router into `backend/main.py`.

## 6. Frontend remediation

- [x] 6.1 Replace `EntityTableDetailsModal.displayedValuesByGroup.affiliation` from `[journal, venue, source_title, publisher, raw_so, _source_name]` to `[]`.
- [x] 6.2 Document the reasoning inline so future maintainers don't reintroduce the buggy values.

## 7. Deployment infrastructure

- [x] 7.1 Remove `.github/workflows/fix-legacy-affiliations.yml` — incompatible with Dokploy's internal Postgres network.
- [x] 7.2 Confirm the admin endpoint covers the same use cases without exposing Postgres externally.
- [x] 7.3 Document the Dokploy shell workflow (`docker exec` + `python -m backend.scripts.fix_legacy_affiliations`).

## 8. Production execution

- [x] 8.1 Deploy commit `3267742` (script + initial migration). Production redeploy: confirmed.
- [x] 8.2 Run `--dry-run`. Result: `scanned=547 matched=497 fixed=437`.
- [x] 8.3 Run `--requeue-enrichment` (first pass). Result: `fixed=437`.
- [x] 8.4 Observe worker fell to Crossref (OpenAlex inactive in cascade). Detect Layer 2 bug.
- [x] 8.5 Deploy commit `22d0d84` (adapter `is_active` contract). Production redeploy: confirmed via cascade dump (`openalex: is_active=True`).
- [x] 8.6 Run `--requeue-enrichment` (second pass). Observe `fixed=44` — detect Layer 3 race.
- [x] 8.7 Deploy commit `ede438e` (migration anti-clobber). Production redeploy: confirmed via test execution in container.
- [x] 8.8 Mark all 437 backed-up entities as `enrichment_status='pending'` to force worker reprocessing through the now-active OpenAlex cascade.
- [x] 8.9 Worker drains: 437 entities re-enriched.
- [x] 8.10 Validate final state.

## 9. Outcome validation

- [x] 9.1 `canonical_affiliations` populated: 350 / 437 (80%).
- [x] 9.2 `author_affiliations` populated: 381 / 437 (87%).
- [x] 9.3 Wrong scalar values cleared: 437 / 437 (100%).
- [x] 9.4 Backups preserved in `_legacy_affiliation_backup`: 437 (reversible).
- [x] 9.5 Residue without affiliation: 56 (13%) — includes 11 genuine preprints (OSF / arXiv / bioRxiv) with no institutional metadata in OpenAlex.
- [x] 9.6 Spot-check entity 25177: wrong value cleared, backup preserved, current state acceptable (OSF preprint, no OpenAlex metadata available).

## 10. Validation

- [x] 10.1 `pytest backend/tests/test_api_import_affiliation_contract.py` (11/11).
- [x] 10.2 `pytest backend/tests/test_enrichment_adapter_contract.py` (17/17).
- [x] 10.3 `pytest backend/tests/test_admin_data_fixes.py` (11/11).
- [x] 10.4 `pytest backend/tests/test_scientific_connectors.py` + `test_enrichment_worker.py` (no regressions).
- [x] 10.5 Frontend `tsc --noEmit` clean.

## 11. Follow-ups (not blocking this change)

- [ ] 11.1 Periodic audit job that scans for `attrs.affiliation` values not present in `canonical_affiliations[].name`. (Pending — depends on alert fatigue review.)
- [ ] 11.2 Frontend refactor to prefer `canonical_affiliations` over `attrs.affiliation` for institution display. (Pending — separate UX change.)
- [ ] 11.3 Cascade improvement: when DOI is present, prefer `search_by_doi` over `search_by_title` to raise OpenAlex match rate beyond 80%. (Pending — research perf trade-off.)
- [ ] 11.4 Retention review for `_legacy_affiliation_backup` keys. (Pending — privacy/storage review.)
