## ADDED Requirements

### Requirement: Data-repair scripts MUST back up cleared values before overwriting
Any UKIP data-repair operation that clears or modifies a field in `attributes_json` SHALL move the prior value into a clearly-namespaced backup key (e.g., `_legacy_<field>_backup`) before clearing. The backup SHALL persist indefinitely as forensic evidence and enables reversibility.

#### Scenario: Legacy affiliation residue is cleared
- **WHEN** `fix_legacy_affiliations.py` removes a wrong `attrs.affiliation` value
- **THEN** the cleared value is written into `attrs._legacy_affiliation_backup` under the corresponding sub-key (`affiliation`, `affiliations`)
- **AND** the script never deletes the value without writing the backup

### Requirement: Data-repair scripts MUST respect the structured data layer
A repair script SHALL NOT treat a field as legacy residue when adjacent structured layers carry data. Specifically, the presence of any entries in `attrs.canonical_affiliations` or `attrs.author_affiliations` is treated as proof that the affiliation was written by a modern code path; the script MUST short-circuit before any comparison or clearing.

#### Scenario: Worker re-enriched after the initial migration
- **WHEN** the migration script scans an entity that already has `attrs.canonical_affiliations` populated by the modern OpenAlex adapter
- **THEN** the script returns without modifying any field
- **AND** the joined display string `attrs.affiliation` is preserved verbatim
- **AND** no backup is created for that entity

#### Scenario: Pure legacy entity from the bug window
- **WHEN** the migration script scans an entity with `attrs.affiliation` set but no `canonical_affiliations` and no `author_affiliations`
- **THEN** the value is treated as legacy residue
- **AND** it is moved to `attrs._legacy_affiliation_backup` and cleared

### Requirement: Data-repair scripts MUST be idempotent
Re-running a repair script after a successful apply SHALL be a no-op. The script SHALL detect already-repaired rows via the presence of `_legacy_*_backup` keys or by re-running its source/value filters and skipping rows that no longer match.

#### Scenario: Operator re-runs the migration after a successful apply
- **WHEN** the migration script runs a second time with `--dry-run` against the same dataset
- **THEN** the reported `fixed` count is 0
- **AND** no entity is modified

### Requirement: Data-repair endpoints MUST be RBAC-gated and audit-logged
HTTP endpoints that trigger destructive data repair SHALL require the `super_admin` role and SHALL emit an audit log line capturing the caller, parameters, and resulting counters.

#### Scenario: Viewer attempts a data-repair call
- **WHEN** a viewer user calls `POST /admin/data-fixes/legacy-affiliations`
- **THEN** the response status is 403
- **AND** no rows are modified

#### Scenario: Super-admin triggers a dry-run
- **WHEN** a super-admin calls the endpoint with `{"dry_run": true}`
- **THEN** the response includes `mode: "dry-run"` and the counter shape `{scanned, matched, fixed}`
- **AND** an audit log line records the caller, the request parameters, and the result
- **AND** no rows are modified
