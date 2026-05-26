## ADDED Requirements

### Requirement: Data-repair operations MUST be idempotent
A repair script SHALL be safe to re-run any number of times. A second `--dry-run` after a successful apply SHALL report `fixed=0`. The script SHALL achieve idempotency by detecting already-repaired rows via the presence of `_legacy_*_backup` keys or by the absence of the bug pattern after the first apply.

#### Scenario: Operator re-runs the migration after a successful apply
- **WHEN** the script runs a second time with `--dry-run` against the same dataset that was just repaired
- **THEN** the reported `scanned` count is unchanged
- **AND** the reported `matched` count is unchanged
- **AND** the reported `fixed` count is 0
- **AND** no entity is modified

#### Scenario: Operator re-runs with `--apply` after a successful apply
- **WHEN** the script runs a second time with mutation enabled against the same dataset
- **THEN** the database state is unchanged
- **AND** no transaction commits any row modifications

### Requirement: Re-run safety MUST survive concurrent worker activity
A repair script SHALL produce stable results even when the enrichment worker is actively re-populating fields between runs. Specifically, a second run after the worker has re-populated `attrs.affiliation` with a joined display string MUST NOT clear that value (see also the structured-layer-guard spec).

#### Scenario: Worker re-enriches between two script runs
- **WHEN** the first run cleared 437 entities, marked them `pending`, and the worker re-populated 44 of them via OpenAlex (writing both joined string and canonical_affiliations) before the second run starts
- **THEN** the second run does not touch any of the 44 re-populated entities
- **AND** the re-populated `attrs.affiliation` values survive verbatim
- **AND** the second run's `fixed` counter excludes those 44 rows

### Requirement: Idempotency MUST hold across orgs and limits
A repair script SHALL produce the same outcome whether it is invoked once against all orgs or invoked per-org sequentially with `--org-id` flags. Likewise, `--limit` partitioning SHALL converge to the same final state as a single unbounded run.

#### Scenario: Operator processes a large corpus in 500-row batches
- **WHEN** the script is invoked repeatedly with `--limit 500` until `fixed=0`
- **THEN** the final database state matches what a single unbounded run would have produced
- **AND** no row is double-backed-up

#### Scenario: Operator processes one org at a time
- **WHEN** the script is invoked once per org with `--org-id N` until all orgs are covered
- **THEN** the union of all org-scoped repairs equals the unbounded run
