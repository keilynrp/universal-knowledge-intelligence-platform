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

#### Scenario: Campus entity is represented
- **WHEN** an institution has a campus-level geographic reference
- **THEN** UKIP can represent it as a campus geographic entity with parent city or region context

#### Scenario: Unknown geographic type is handled
- **WHEN** a geographic reference cannot be classified into country, region, city, campus, address, or spatial_area
- **THEN** UKIP assigns type `unknown` and preserves the raw text with provenance

### Requirement: Geographic entities preserve identifiers and coordinates
Geographic entities SHALL preserve available external identifiers and georeferencing data.

#### Scenario: Entity has coordinates
- **WHEN** latitude and longitude are available
- **THEN** the geographic entity stores those coordinates with provenance

#### Scenario: Entity has external IDs
- **WHEN** GeoNames, Wikidata, ISO, or OSM identifiers are available
- **THEN** the geographic entity preserves those identifiers

#### Scenario: ISO country code is normalized
- **WHEN** a geographic entity represents a country
- **THEN** the `country_code` field contains a valid ISO 3166-1 alpha-2 code
- **AND** a normalization helper validates and uppercases the code

#### Scenario: GeoNames ID is normalized
- **WHEN** a geographic entity has a GeoNames reference
- **THEN** the `geonames_id` field contains a numeric GeoNames identifier as a string

#### Scenario: Wikidata QID is normalized
- **WHEN** a geographic entity has a Wikidata reference
- **THEN** the `wikidata_id` field contains a valid QID (e.g., Q90 for Paris)

#### Scenario: OSM ID is normalized
- **WHEN** a geographic entity has an OpenStreetMap reference
- **THEN** the `osm_id` field contains the OSM identifier with type prefix (e.g., R123456)

### Requirement: Geographic entities support hierarchy
Geographic entities SHALL support parent-child hierarchy relationships.

#### Scenario: City has parent country
- **WHEN** a city geographic entity is created with known country context
- **THEN** the entity parent_id references the country geographic entity

#### Scenario: Region has parent country
- **WHEN** a region geographic entity is created
- **THEN** the entity parent_id references the country geographic entity

#### Scenario: Campus has parent city
- **WHEN** a campus geographic entity is created with known city context
- **THEN** the entity parent_id references the city geographic entity

#### Scenario: Hierarchy is traversable
- **WHEN** a geographic entity has a parent_id
- **THEN** the parent entity can be retrieved and its own parent_id followed to construct the full hierarchy chain

### Requirement: Geographic entities support aliases
Geographic entities SHALL support alias names for multilingual and variant name resolution.

#### Scenario: Country has multilingual aliases
- **WHEN** a country geographic entity is created
- **THEN** the aliases list may include variant names in multiple languages (e.g., "Germany", "Deutschland", "Alemania")

#### Scenario: City has variant names
- **WHEN** a city geographic entity is created
- **THEN** the aliases list may include transliterations and historical names

### Requirement: Geographic entity shapes are testable
UKIP SHALL support tests for valid, partial, and invalid geographic entity shapes.

#### Scenario: Valid country entity passes validation
- **WHEN** a geographic entity has type `country`, a valid ISO country code, and a name
- **THEN** it passes schema validation

#### Scenario: Partial entity with only name and type passes validation
- **WHEN** a geographic entity has a name and type but no external identifiers or coordinates
- **THEN** it passes schema validation with reduced confidence

#### Scenario: Entity without name or type fails validation
- **WHEN** a geographic entity is missing both name and type
- **THEN** it fails schema validation

#### Scenario: Invalid ISO code is rejected
- **WHEN** a geographic entity specifies a country_code that is not a valid ISO 3166-1 alpha-2 code
- **THEN** the identifier normalization helper rejects it or flags it for review
