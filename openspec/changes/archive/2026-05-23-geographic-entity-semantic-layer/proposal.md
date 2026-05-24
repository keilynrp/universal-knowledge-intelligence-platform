## Why

UKIP's scientific intelligence model needs geography as a first-class semantic layer. Today geographic information often appears as free text inside affiliations, addresses, country strings, imported columns, or enrichment payloads. That is not enough for reliable institutional, regional, or geospatial intelligence.

Research stakeholders need to answer questions like:

- Which regions or countries concentrate a portfolio's production?
- Which institutions collaborate across borders?
- Which research themes are emerging in specific geographies?
- Which datasets, projects, publications, or organizations cover a geographic area?
- Which claims are supported by geocoded evidence rather than brittle string parsing?

To support this, UKIP needs normalized geographic entities with explicit identifiers, hierarchy, georeferencing, provenance, and relationships.

## What Changes

- **New**: Geographic entity semantic layer for places, countries, regions, cities, campuses, addresses, and spatial coverage.
- **New**: Geographic authority identifiers aligned with ISO 3166, GeoNames, Wikidata, schema.org Place, DCAT spatial coverage, EDM Place, BIBFRAME Place, and future GeoSPARQL.
- **New**: Geocoding/reconciliation contract that turns raw place strings and affiliation-derived geography into normalized geographic entities.
- **New**: Relationship model connecting organizations, persons, publications, datasets, projects, events, and concepts to geographic entities.
- **Modified**: Existing geographic analytics should consume normalized geographic entities when available and fall back to text parsing only when necessary.

## Capabilities

### New Capabilities

- `geographic-entity-model`: Canonical model for geographic entities and spatial identifiers.
- `geographic-reconciliation-service`: Resolve place strings/country codes/affiliation geography into canonical geographic entities.
- `geographic-relationship-contract`: Standard relationships between domain entities and geographic entities.
- `linked-data-geographic-alignment`: Alignment with GeoNames, Wikidata, ISO, schema.org Place, DCAT spatial, EDM Place, BIBFRAME Place, and future GeoSPARQL.

### Modified Capabilities

- `scientific-affiliation-contract`: Structured affiliations can produce organization-country/city relations.
- `institution-affiliation-reconciliation`: Resolved institutions can link to normalized geographic entities.
- `dashboard-summary`: Geographic analytics should prefer normalized geographic entities over free-text affiliation parsing.

## Impact

- **Data model**: Add or define canonical geographic entity structures and relationships.
- **Backend**: Reconciliation/geocoding service, identifier normalization helpers, and graph/entity relationship materialization.
- **Frontend**: Future maps, geographic evidence panels, regional filters, and stakeholder report sections.
- **Linked Data**: UKIP can export place semantics into JSON-LD/RDF-compatible structures.
- **Tests**: Add contract tests for place normalization, identifier matching, hierarchy, and geographic relationships.

## Success Criteria

- UKIP can represent countries, regions, cities, campuses, addresses, and spatial coverage as explicit entities.
- UKIP can link an organization to a normalized place using country/city/geocode evidence.
- UKIP can distinguish raw geographic text from reconciled geographic identity.
- Geographic analytics can operate on normalized country/city identifiers when available.
- Future linked-data exports can express place semantics without reparsing raw strings.
