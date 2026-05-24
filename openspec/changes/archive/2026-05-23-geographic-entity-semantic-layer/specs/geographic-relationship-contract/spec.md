## ADDED Requirements

### Requirement: UKIP links domain entities to geographic entities
UKIP SHALL support semantic relationships between geographic entities and organizations, persons, publications, datasets, projects, events, and concepts.

#### Scenario: Organization has location
- **WHEN** an institution has resolved country/city metadata
- **THEN** UKIP can create an `organization located_in geographic_entity` relationship

#### Scenario: Publication has affiliation geography
- **WHEN** a publication author affiliations resolve to geographic entities
- **THEN** UKIP can create `publication associated_with geographic_entity` relationships

#### Scenario: Dataset has spatial coverage
- **WHEN** a dataset includes spatial coverage
- **THEN** UKIP can create a `dataset covers_region geographic_entity` relationship

#### Scenario: Person is affiliated in a geographic location
- **WHEN** a person entity has affiliation data that resolves to a geographic entity
- **THEN** UKIP can create a `person affiliated_in geographic_entity` relationship

#### Scenario: Project is funded in a geographic location
- **WHEN** a project or grant record includes funder country or location
- **THEN** UKIP can create a `project funded_in geographic_entity` relationship

#### Scenario: Event is held at a geographic location
- **WHEN** an event record includes a venue location that resolves to a geographic entity
- **THEN** UKIP can create an `event held_at geographic_entity` relationship

#### Scenario: Concept is prevalent in a geographic area
- **WHEN** analytics determine that a concept or topic has significant concentration in a geographic area
- **THEN** UKIP can create a `concept prevalent_in geographic_entity` relationship with evidence

#### Scenario: Geographic entity is contained in another
- **WHEN** a geographic entity has a parent in the hierarchy
- **THEN** UKIP can represent this as a `geographic_entity contained_in geographic_entity` relationship

### Requirement: Geographic relationships preserve confidence and provenance
Geographic relationships SHALL include confidence and evidence metadata.

#### Scenario: Relationship is inferred from affiliation
- **WHEN** a relationship is created from affiliation-derived geography
- **THEN** the relationship records the source field/provider and confidence score

#### Scenario: Relationship is inferred from authority resolution
- **WHEN** a relationship is created because an institution was resolved via ROR and the ROR record includes country
- **THEN** the relationship records ROR as the evidence source and inherits the authority resolution confidence

#### Scenario: Relationship is inferred from imported column
- **WHEN** a relationship is created from an imported geographic column
- **THEN** the relationship records the column name, original value, and extraction method

### Requirement: Organization located_in relationships are materialized from institution geography
UKIP SHALL materialize `organization located_in geographic_entity` relationships when institution reconciliation resolves geographic metadata.

#### Scenario: ROR-resolved institution has country
- **WHEN** an institution is resolved via ROR and the ROR record includes country code
- **THEN** UKIP materializes an `organization located_in` relationship to the corresponding country entity

#### Scenario: Affiliation-derived institution has city and country
- **WHEN** affiliation parsing extracts both city and country for an institution
- **THEN** UKIP materializes `organization located_in` relationships to both the city and country entities

### Requirement: Publication associated_with relationships are materialized from author affiliations
UKIP SHALL materialize `publication associated_with geographic_entity` relationships when author affiliations resolve to geographic entities.

#### Scenario: Publication with single-country affiliations
- **WHEN** all author affiliations on a publication resolve to the same country
- **THEN** UKIP materializes a single `publication associated_with` relationship to that country

#### Scenario: Publication with multi-country affiliations
- **WHEN** author affiliations on a publication resolve to multiple countries
- **THEN** UKIP materializes `publication associated_with` relationships to each distinct country

### Requirement: Dataset covers_region relationships are materialized from spatial coverage
UKIP SHALL materialize `dataset covers_region geographic_entity` relationships when datasets include spatial coverage metadata.

#### Scenario: Dataset has explicit spatial coverage
- **WHEN** a dataset record includes spatial coverage that resolves to one or more geographic entities
- **THEN** UKIP materializes `dataset covers_region` relationships to each resolved entity

### Requirement: Geographic relationship tests verify provenance and confidence
UKIP SHALL include tests that verify geographic relationships carry correct provenance and confidence metadata.

#### Scenario: Test verifies located_in relationship provenance
- **WHEN** a test creates an organization with ROR-resolved country
- **THEN** the resulting `located_in` relationship includes ROR as evidence source and a confidence score

#### Scenario: Test verifies associated_with relationship from affiliation
- **WHEN** a test creates a publication with author affiliations that resolve to geographic entities
- **THEN** the resulting `associated_with` relationships include the affiliation text as evidence

#### Scenario: Test verifies covers_region relationship from spatial coverage
- **WHEN** a test creates a dataset with spatial coverage
- **THEN** the resulting `covers_region` relationship includes the spatial coverage value as evidence
