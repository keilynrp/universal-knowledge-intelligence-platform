## ADDED Requirements

### Requirement: Geographic entities align with Linked Data place standards
UKIP geographic entities SHALL be representable in Linked Data-compatible forms aligned with schema.org Place, DCAT spatial coverage, EDM Place, BIBFRAME Place, and future GeoSPARQL.

#### Scenario: Entity is exported as schema.org Place
- **WHEN** a geographic entity is exported to JSON-LD
- **THEN** it can be represented as a schema.org Place with name, identifiers, and coordinates when available

#### Scenario: Dataset spatial coverage is exported
- **WHEN** a dataset has geographic coverage
- **THEN** it can be represented using a DCAT-compatible spatial coverage mapping

#### Scenario: Bibliographic place is exported
- **WHEN** a bibliographic record has place semantics
- **THEN** it can be mapped to a BIBFRAME-compatible Place representation

### Requirement: Geometry fields remain future-compatible with GeoSPARQL
UKIP SHALL keep optional geometry metadata compatible with future GeoSPARQL-style exports.

#### Scenario: Geometry is available
- **WHEN** a geographic entity has geometry
- **THEN** UKIP stores it in a structured geometry field with provenance
