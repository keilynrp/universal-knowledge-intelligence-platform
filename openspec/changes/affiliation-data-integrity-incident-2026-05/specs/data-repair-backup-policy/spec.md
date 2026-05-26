## ADDED Requirements

### Requirement: Data-repair operations MUST back up cleared values before overwriting
Any data-repair script or endpoint that clears or modifies a field in `attributes_json` SHALL move the prior value into a clearly-namespaced backup key (`_legacy_<field>_backup`) before clearing. The backup SHALL persist indefinitely as forensic evidence and to enable reversibility.

#### Scenario: Legacy scalar affiliation is cleared
- **WHEN** `fix_legacy_affiliations.py` removes a value from `attrs.affiliation`
- **THEN** the cleared value is written into `attrs._legacy_affiliation_backup.affiliation` first
- **AND** the script's commit places the backup write and the clear into the same transaction

#### Scenario: Both scalar and list variants of affiliation are cleared
- **WHEN** the script clears both `attrs.affiliation` (string) and `attrs.affiliations` (list)
- **THEN** the backup contains both sub-keys: `_legacy_affiliation_backup.affiliation` (string) and `_legacy_affiliation_backup.affiliations` (list)
- **AND** types in the backup match the types of the original values

#### Scenario: Repeated repair on the same entity
- **WHEN** the script processes an entity that was already repaired (and therefore already has `_legacy_affiliation_backup`)
- **THEN** the script does not overwrite the existing backup with a new, possibly-empty value
- **AND** the original forensic record remains intact

### Requirement: Backup keys MUST never be exposed by read endpoints
Backup keys under `_legacy_*_backup` SHALL be filtered out of any HTTP response that serializes `attributes_json` to clients. They are internal forensic markers, not user-facing data.

#### Scenario: Frontend fetches entity 25177 via `/entities/{id}`
- **WHEN** the API serializes entity 25177's `attributes_json`
- **THEN** keys matching `_legacy_*_backup` are omitted from the response payload
- **AND** the data they reference remains present in the database

#### Scenario: Operator queries entity directly via the database
- **WHEN** a super-admin runs a SQL query against `raw_entities.attributes_json`
- **THEN** the `_legacy_affiliation_backup` is visible in the raw row
- **AND** can be used for forensic audit or manual restoration
