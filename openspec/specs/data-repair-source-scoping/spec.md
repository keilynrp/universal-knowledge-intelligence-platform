# data-repair-source-scoping Specification

## Purpose
TBD - created by archiving change affiliation-data-integrity-incident-2026-05. Update Purpose after archive.
## Requirements
### Requirement: Data-repair operations MUST restrict to provenance-affected sources
A repair script targeting a specific incident SHALL restrict its scan to entities whose `enrichment_source` matches the providers known to be affected by the underlying bug. Entities from unrelated sources (CSV uploads, store imports, manual entries) SHALL be ignored even if their data superficially matches the bug pattern.

#### Scenario: Entity from a CSV upload has a suspicious-looking affiliation
- **WHEN** `fix_legacy_affiliations.py` encounters an entity with `enrichment_source = "csv_upload"` and `attrs.affiliation = "Journal of Something"` (string that looks like a journal name)
- **THEN** the entity is not modified
- **AND** the script's `matched` counter does not increment for this row
- **AND** the value is preserved verbatim

#### Scenario: Entity from a store integration
- **WHEN** the script encounters an entity from a commerce/store source with the same superficial pattern
- **THEN** the entity is not modified
- **AND** the script does not infer a bug pattern from the value shape

### Requirement: Source matching MUST be case-insensitive
Affected source identifiers SHALL be matched case-insensitively to handle historical inconsistencies (`OpenAlex`, `openalex`, `OPENALEX` should all match the same canonical provider).

#### Scenario: Historical entities have `enrichment_source = "OpenAlex"` with capital letters
- **WHEN** the script reads an entity with `enrichment_source = "OpenAlex"`
- **THEN** the lowercased value `openalex` is found in the affected-sources set
- **AND** the entity is included in the scan

#### Scenario: A whitespace-padded source value
- **WHEN** the script reads an entity with `enrichment_source = "  openalex  "`
- **THEN** the value is stripped before comparison
- **AND** the entity is included in the scan

### Requirement: The affected-sources set MUST be explicit and reviewable
The list of affected provider names SHALL live in a single named constant in the script source (`_AFFECTED_SOURCES`) so a reviewer can audit which providers a repair operation touches without reading the code logic.

#### Scenario: A future repair targets a different provider
- **WHEN** a new repair script is added for a different incident
- **THEN** the script declares its own `_AFFECTED_SOURCES` constant at module scope
- **AND** the constant value is reviewable in a single `grep` of the file

