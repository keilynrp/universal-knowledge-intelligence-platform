## ADDED Requirements

### Requirement: Linked-data outputs are generated from canonical semantics
UKIP SHALL generate JSON-LD/RDF-compatible outputs from governed canonical semantics rather than raw provider payloads.

#### Scenario: Entity is exported as JSON-LD
- **WHEN** UKIP exports an entity as JSON-LD
- **THEN** the output uses canonical entity identity, labels, relationships, provenance, and declared linked-data mappings
- **AND** provider-specific payload fields appear only when explicitly modeled as observations or provenance

#### Scenario: Relationship is exported
- **WHEN** UKIP exports a relationship to a linked-data format
- **THEN** the relationship uses a governed predicate mapping
- **AND** includes evidence or provenance when available

### Requirement: UKIP aligns canonical semantics with external models
UKIP SHALL define explicit alignment mappings from canonical semantics to external linked-data models when applicable.

#### Scenario: Bibliographic resource is exported
- **WHEN** a publication or bibliographic resource is exported
- **THEN** UKIP maps applicable canonical fields to BIBFRAME-compatible terms

#### Scenario: Cultural heritage aggregation is exported
- **WHEN** a cultural heritage or aggregation-oriented resource is exported
- **THEN** UKIP maps applicable canonical fields to Europeana EDM-compatible terms

#### Scenario: General web entity is exported
- **WHEN** a general organization, person, place, dataset, or creative work is exported
- **THEN** UKIP maps applicable canonical fields to schema.org-compatible terms
