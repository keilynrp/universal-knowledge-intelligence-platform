## ADDED Requirements

### Requirement: UKIP supports canonical geographic entities
UKIP SHALL define a canonical geographic entity model for countries, regions, cities, campuses, addresses, and spatial areas.

#### Scenario: Country entity is represented
- **WHEN** UKIP receives a country code or country name
- **THEN** it can represent the country as a geographic entity with normalized country code and provenance

#### Scenario: City entity is represented
- **WHEN** UKIP receives a city with country context
- **THEN** it can represent the city as a geographic entity with parent country context

#### Scenario: Spatial coverage is represented
- **WHEN** a dataset or source record describes spatial coverage
- **THEN** UKIP can represent that coverage as a geographic entity or spatial area

### Requirement: Geographic entities preserve identifiers and coordinates
Geographic entities SHALL preserve available external identifiers and georeferencing data.

#### Scenario: Entity has coordinates
- **WHEN** latitude and longitude are available
- **THEN** the geographic entity stores those coordinates with provenance

#### Scenario: Entity has external IDs
- **WHEN** GeoNames, Wikidata, ISO, or OSM identifiers are available
- **THEN** the geographic entity preserves those identifiers
