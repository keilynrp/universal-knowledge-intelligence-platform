# data-repair-structured-layer-guard Specification

## Purpose
TBD - created by archiving change affiliation-data-integrity-incident-2026-05. Update Purpose after archive.
## Requirements
### Requirement: Data-repair operations MUST short-circuit when structured layers carry data
A repair script SHALL skip an entity without modification when `attrs.canonical_affiliations` or `attrs.author_affiliations` contains any entries. Their presence is causal proof that the affiliation data came from the modern code path — the bug-era code (cbe3255) never wrote those layers.

#### Scenario: Entity has both joined display string and canonical_affiliations
- **WHEN** the script encounters an entity with `attrs.affiliation = "Stockholm University, SE; Columbia University, US"` and `attrs.canonical_affiliations = [{name: "Stockholm University", country_code: "SE"}, ...]`
- **THEN** the script returns without modifying the entity
- **AND** the joined string is preserved verbatim
- **AND** no `_legacy_affiliation_backup` key is created
- **AND** the script's `fixed` counter does not increment

#### Scenario: Entity has only author_affiliations (canonical_affiliations absent)
- **WHEN** the script encounters an entity with `attrs.affiliation` set, no `canonical_affiliations`, but `attrs.author_affiliations = [{author_name: "Doe", institutions: [{name: "MIT"}]}]`
- **THEN** the script returns without modifying the entity
- **AND** the author-level structured layer is enough proof of modern provenance

#### Scenario: Both structured layers are present
- **WHEN** the script encounters an entity with both layers populated
- **THEN** the short-circuit triggers on the first present layer
- **AND** the second check is not required to also pass

### Requirement: The structured-layer guard MUST trigger on any non-empty value, not just well-formed dicts
The guard SHALL fire when the structured-layer key exists in `attrs` and its value is a list of length ≥ 1, regardless of whether each item is a fully-formed dict. The intent is to capture "anything written by the modern path", not to validate the schema.

#### Scenario: Structured layer contains a partially-formed entry
- **WHEN** the script encounters `attrs.canonical_affiliations = [{name: "MIT"}]` (no country_code, no ROR)
- **THEN** the guard fires
- **AND** the entity is skipped — the script does not parse the entry to decide

#### Scenario: Structured layer is an empty list
- **WHEN** the script encounters `attrs.canonical_affiliations = []`
- **THEN** the guard does NOT fire (empty list is not "data present")
- **AND** the script proceeds with normal legacy detection logic

#### Scenario: Structured layer key is set to `null`
- **WHEN** the script encounters `attrs.canonical_affiliations = null`
- **THEN** the guard does NOT fire
- **AND** the script proceeds with normal legacy detection logic

