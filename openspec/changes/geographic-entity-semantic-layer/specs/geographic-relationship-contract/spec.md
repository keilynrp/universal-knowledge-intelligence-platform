## ADDED Requirements

### Requirement: UKIP links domain entities to geographic entities
UKIP SHALL support semantic relationships between geographic entities and organizations, persons, publications, datasets, projects, events, and concepts.

#### Scenario: Organization has location
- **WHEN** an institution has resolved country/city metadata
- **THEN** UKIP can create an `organization located_in geographic_entity` relationship

#### Scenario: Publication has affiliation geography
- **WHEN** a publication's author affiliations resolve to geographic entities
- **THEN** UKIP can create `publication associated_with geographic_entity` relationships

#### Scenario: Dataset has spatial coverage
- **WHEN** a dataset includes spatial coverage
- **THEN** UKIP can create a `dataset covers_region geographic_entity` relationship

### Requirement: Geographic relationships preserve confidence and provenance
Geographic relationships SHALL include confidence and evidence metadata.

#### Scenario: Relationship is inferred from affiliation
- **WHEN** a relationship is created from affiliation-derived geography
- **THEN** the relationship records the source field/provider and confidence score
