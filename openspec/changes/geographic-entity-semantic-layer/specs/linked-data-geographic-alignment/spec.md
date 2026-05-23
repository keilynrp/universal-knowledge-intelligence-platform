## ADDED Requirements

### Requirement: Geographic entities align with Linked Data place standards
UKIP geographic entities SHALL be representable in Linked Data-compatible forms aligned with schema.org Place, DCAT spatial coverage, EDM Place, BIBFRAME Place, and future GeoSPARQL.

#### Scenario: Entity is exported as schema.org Place
- **WHEN** a geographic entity is exported to JSON-LD
- **THEN** it can be represented as a schema.org Place with name, identifiers, and coordinates when available

#### Scenario: schema.org Place includes geo property
- **WHEN** a geographic entity has latitude and longitude
- **THEN** the schema.org Place representation includes a `geo` property with `latitude` and `longitude` as schema.org GeoCoordinates

#### Scenario: schema.org Place includes identifiers as sameAs
- **WHEN** a geographic entity has Wikidata QID, GeoNames ID, or OSM ID
- **THEN** the schema.org Place representation includes `sameAs` links to the corresponding external URIs

#### Scenario: schema.org Place includes containedInPlace for hierarchy
- **WHEN** a geographic entity has a parent entity
- **THEN** the schema.org Place representation includes a `containedInPlace` reference to the parent

### Requirement: Dataset spatial coverage aligns with DCAT
UKIP SHALL represent dataset geographic coverage using DCAT-compatible spatial coverage mappings.

#### Scenario: Dataset spatial coverage is exported
- **WHEN** a dataset has geographic coverage
- **THEN** it can be represented using a DCAT-compatible spatial coverage mapping

#### Scenario: DCAT spatial uses dcterms:spatial with place URI
- **WHEN** a dataset geographic coverage resolves to a geographic entity with a Wikidata or GeoNames URI
- **THEN** the DCAT representation uses `dcterms:spatial` with the external URI as the spatial value

#### Scenario: DCAT spatial uses bounding box when coordinates are available
- **WHEN** a dataset geographic coverage includes bounding coordinates or a geometry
- **THEN** the DCAT representation can include a `dcat:bbox` property with the bounding geometry

### Requirement: Bibliographic place semantics align with BIBFRAME and EDM
UKIP SHALL represent bibliographic and cultural heritage place semantics using BIBFRAME Place and Europeana EDM Place mappings where applicable.

#### Scenario: Bibliographic place is exported as BIBFRAME Place
- **WHEN** a bibliographic record has place semantics (e.g., publication place, geographic subject)
- **THEN** it can be mapped to a BIBFRAME-compatible Place representation

#### Scenario: Cultural heritage place is exported as EDM Place
- **WHEN** a cultural heritage or digital object record has place semantics
- **THEN** it can be mapped to an EDM Place representation with `skos:prefLabel` and optional coordinates

#### Scenario: EDM Place includes owl:sameAs for linked identifiers
- **WHEN** a geographic entity mapped as EDM Place has external identifiers
- **THEN** the EDM representation includes `owl:sameAs` links to GeoNames, Wikidata, or other authority URIs

#### Scenario: BIBFRAME Place includes identifiers
- **WHEN** a geographic entity mapped as BIBFRAME Place has external identifiers
- **THEN** the BIBFRAME representation includes `bf:identifiedBy` entries for ISO codes, GeoNames IDs, or Wikidata QIDs

### Requirement: Geometry fields remain future-compatible with GeoSPARQL
UKIP SHALL keep optional geometry metadata compatible with future GeoSPARQL-style exports.

#### Scenario: Geometry is available
- **WHEN** a geographic entity has geometry
- **THEN** UKIP stores it in a structured geometry field with provenance

#### Scenario: Geometry field uses GeoJSON-compatible structure
- **WHEN** a geographic entity stores geometry
- **THEN** the geometry field uses a GeoJSON-compatible structure (type + coordinates)
- **AND** this structure can be converted to WKT for future GeoSPARQL serialization

#### Scenario: Point geometry is derivable from coordinates
- **WHEN** a geographic entity has latitude and longitude but no explicit geometry
- **THEN** a GeoJSON Point geometry can be derived from the coordinates for export purposes

#### Scenario: GeoSPARQL export path is documented
- **WHEN** UKIP documents its linked-data alignment strategy
- **THEN** it includes a future-ready path for representing geographic entities as `geo:Feature` with `geo:hasGeometry` and `geo:asWKT` properties
- **AND** no current field structure prevents this future alignment

### Requirement: Geographic analytics prefer normalized geographic entities
UKIP geographic analytics SHALL prefer normalized geographic entity metadata over raw affiliation text parsing when normalized data is available.

#### Scenario: Geographic counts use normalized country codes
- **WHEN** geographic analytics compute country-level publication or entity counts
- **THEN** they prefer counts derived from normalized geographic entity relationships
- **AND** fall back to affiliation text parsing only when no normalized geographic data exists

#### Scenario: Fallback to affiliation text parsing is preserved
- **WHEN** an entity has no normalized geographic metadata
- **THEN** existing affiliation text parsing logic continues to provide geographic signals
- **AND** the fallback results are distinguishable from normalized results in analytics output

#### Scenario: Dashboard geographic visualization uses normalized data
- **WHEN** a dashboard or report renders geographic distribution
- **THEN** it prefers normalized geographic entity data
- **AND** includes a future-ready contract for map-based visualization without building the map UI in this change

#### Scenario: API test proves normalized country codes drive geographic counts
- **WHEN** a test creates entities with both normalized geographic entities and raw affiliation text
- **THEN** geographic analytics endpoints return counts derived from normalized geographic data
- **AND** the test verifies that raw affiliation fallback does not double-count entities that have normalized geographic data
