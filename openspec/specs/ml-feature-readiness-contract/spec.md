# ml-feature-readiness-contract Specification

## Purpose
TBD - created by archiving change retrospective-intelligence-layer. Update Purpose after archive.
## Requirements
### Requirement: Feature datasets use point-in-time envelopes

The system SHALL generate feature datasets with `dataset_id`,
`dataset_version`, `org_scope`, `subject_type`, `subject_id`,
`feature_timestamp`, `label_timestamp`, `features`, `labels`, `lineage`,
`schema_version`, and `created_at`.

#### Scenario: Feature timestamp precedes label timestamp

- **WHEN** a supervised dataset row is generated
- **THEN** `feature_timestamp` is earlier than or equal to the prediction time
- **AND** `label_timestamp` is later than the feature timestamp

### Requirement: Feature generation prevents time leakage

The system SHALL exclude feature values that were not available at or before
the feature timestamp.

#### Scenario: Later enrichment is excluded

- **WHEN** an entity was enriched after the feature timestamp
- **THEN** enrichment values from that later event are not included in the
  feature row

### Requirement: Labels come from governed outcomes

The system SHALL derive labels only from governed decisions, validated outcomes,
or explicitly approved proxy outcomes with lineage.

#### Scenario: Authority decision creates a label

- **WHEN** an authorized reviewer accepts an authority candidate
- **THEN** a future feature dataset may use that decision as a positive label
  with reviewer role, timestamp, and decision lineage

### Requirement: Feature rows include provenance lineage

The system SHALL retain lineage from feature rows to historical events,
snapshots, source systems, and transformation versions.

#### Scenario: Feature row can be traced

- **WHEN** a model training row includes NIF Bayes and authority readiness
  features
- **THEN** the row lineage identifies the historical metric snapshot and
  authority snapshot used to compute those features

### Requirement: Initial ML output is offline dataset validation

The first implementation SHALL produce offline feature datasets for validation
and review, not train, deploy, or serve models.

#### Scenario: Dataset is generated before model training exists

- **WHEN** the first feature dataset is created
- **THEN** UKIP records dataset quality, row counts, lineage completeness, and
  leakage-check results
- **AND** no model endpoint is created as part of that workflow

