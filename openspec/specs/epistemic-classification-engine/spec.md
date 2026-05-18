## ADDED Requirements

### Requirement: Domain schema supports epistemology configuration
The system SHALL accept an optional `epistemology` section in domain YAML files containing paradigm definitions and evidence hierarchy levels. Domains without this section SHALL continue to function without epistemic features.

#### Scenario: Science domain with epistemology config
- **WHEN** `science.yaml` contains an `epistemology` key with paradigms and evidence_hierarchy
- **THEN** `DomainSchema` parses and exposes the epistemology configuration via `schema.epistemology`

#### Scenario: Domain without epistemology config
- **WHEN** a domain YAML file does not contain an `epistemology` key
- **THEN** `schema.epistemology` SHALL be `None` and all other domain features work unchanged

### Requirement: Paradigm definition structure
Each paradigm in the epistemology configuration SHALL have an `id`, `label`, `description`, and `indicators` block. Indicators SHALL include `terms` (list of strings), `document_types` (list of strings), and `journals_affinity` (list of strings).

#### Scenario: Valid paradigm with all indicator types
- **WHEN** a paradigm is defined with terms, document_types, and journals_affinity indicators
- **THEN** the classifier uses all three indicator types with weights 0.6 (terms), 0.25 (document_types), 0.15 (journals_affinity)

#### Scenario: Paradigm with only term indicators
- **WHEN** a paradigm has terms but empty document_types and journals_affinity lists
- **THEN** the classifier uses only term matching with the term weight renormalized to 1.0

### Requirement: Epistemic classifier scores entities against paradigms
The system SHALL classify enriched entities by computing a normalized affinity score vector across all configured paradigms. Term matching SHALL be case-insensitive and match whole words or multi-word phrases in the abstract and enrichment_concepts fields.

#### Scenario: Entity with abstract matching empiricist terms
- **WHEN** an entity has abstract containing "randomized controlled trial" and "statistical significance"
- **AND** the domain has paradigms empiricist (with those terms) and constructivist (with "discourse analysis", "ethnography")
- **THEN** the entity receives a higher empiricist score than constructivist score
- **AND** scores are normalized to sum to 1.0

#### Scenario: Entity with no abstract or abstract shorter than 50 characters
- **WHEN** an entity has no abstract or abstract length < 50 characters
- **THEN** the classifier SHALL mark the entity as `unclassified` with empty paradigm scores

#### Scenario: Entity matching no paradigm indicators
- **WHEN** an entity's abstract and concepts match zero indicators across all paradigms
- **THEN** the entity SHALL be marked as `unclassified`

### Requirement: Epistemic profile persistence
The classifier SHALL persist results in `attributes_json.epistemic_profile` with keys: `paradigms` (dict of id→score), `dominant` (highest-scoring paradigm id or "unclassified"), and `classified_at` (ISO timestamp).

#### Scenario: Profile stored after classification
- **WHEN** an entity is classified with scores empiricist=0.72, constructivist=0.18, critical=0.10
- **THEN** `attributes_json.epistemic_profile.paradigms` equals `{"empiricist": 0.72, "constructivist": 0.18, "critical": 0.10}`
- **AND** `attributes_json.epistemic_profile.dominant` equals `"empiricist"`

#### Scenario: Re-classification overwrites previous profile
- **WHEN** an entity already has an epistemic_profile and is classified again
- **THEN** the previous profile is replaced with the new one

### Requirement: Batch classification endpoint
The system SHALL provide `POST /analytics/epistemic/{domain_id}/classify` (admin+ role) that classifies all enriched entities in the domain that lack an epistemic profile.

#### Scenario: Batch classify entities without profile
- **WHEN** admin calls POST /analytics/epistemic/science/classify
- **AND** there are 100 enriched entities without epistemic_profile
- **THEN** the system classifies all 100 and returns `{"classified": 100, "skipped": 0, "unclassified": 5}`

#### Scenario: Viewer cannot trigger batch classification
- **WHEN** a viewer role user calls POST /analytics/epistemic/science/classify
- **THEN** the system returns HTTP 403

#### Scenario: Domain without epistemology config
- **WHEN** admin calls POST /analytics/epistemic/healthcare/classify
- **AND** healthcare domain has no epistemology configuration
- **THEN** the system returns HTTP 400 with message indicating no paradigms configured

### Requirement: Post-enrichment auto-classification
After successful enrichment of an entity, the system SHALL automatically classify it if the entity's domain has epistemology configuration.

#### Scenario: Auto-classify after enrichment
- **WHEN** an entity in the science domain is successfully enriched
- **AND** science domain has epistemology configuration with paradigms
- **THEN** the entity's `attributes_json.epistemic_profile` is populated before the enrichment transaction commits

#### Scenario: Skip auto-classification for domains without epistemology
- **WHEN** an entity in the healthcare domain is successfully enriched
- **AND** healthcare domain has no epistemology configuration
- **THEN** no epistemic classification occurs and enrichment completes normally

### Requirement: Epistemic distribution endpoint
The system SHALL provide `GET /analytics/epistemic/{domain_id}/distribution` (authenticated) returning paradigm distribution statistics.

#### Scenario: Distribution with temporal breakdown
- **WHEN** user calls GET /analytics/epistemic/science/distribution
- **THEN** the response includes `total_classified`, `total_unclassified`, `paradigm_counts` (dict), and `by_year` (list of {year, paradigm_counts})

#### Scenario: Empty distribution for domain without classified entities
- **WHEN** user calls GET /analytics/epistemic/science/distribution
- **AND** no entities have epistemic profiles
- **THEN** the response has `total_classified: 0` and empty `paradigm_counts`

### Requirement: OLAP paradigm dimension
The OLAP cube SHALL include `paradigm` as an available dimension derived from `attributes_json.epistemic_profile.dominant`.

#### Scenario: Cross-tabulate paradigm with year
- **WHEN** user queries the OLAP cube with group_by=["paradigm", "year"]
- **THEN** results show entity counts grouped by dominant paradigm and publication year

#### Scenario: Filter by specific paradigm
- **WHEN** user queries the OLAP cube with filter paradigm="empiricist"
- **THEN** only entities with dominant paradigm "empiricist" are included
