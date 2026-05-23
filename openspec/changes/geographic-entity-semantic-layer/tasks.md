## 1. Geographic entity contract

- [x] 1.1 Define `GeographicEntity` schema/model contract with type, identifiers, coordinates, hierarchy, confidence, and provenance.
- [x] 1.2 Define accepted geographic entity types: country, region, city, campus, address, spatial_area, unknown.
- [x] 1.3 Define identifier normalization helpers for ISO country codes, GeoNames IDs, Wikidata QIDs, and OSM IDs.
- [x] 1.4 Add tests for valid and partial geographic entity shapes.

## 2. Geographic candidate extraction

- [x] 2.1 Extract country/city/region candidates from structured affiliations.
- [x] 2.2 Extract geography from imported columns with names like country, city, region, address, latitude, longitude.
- [x] 2.3 Extract dataset spatial coverage fields when available.
- [x] 2.4 Preserve raw text and source field as candidate evidence.
- [x] 2.5 Add tests for structured affiliation and imported-column candidate extraction.

## 3. Reconciliation and confidence

- [x] 3.1 Implement ISO country normalization as the first deterministic reconciliation path.
- [x] 3.2 Add place name normalization and alias-ready matching helper.
- [x] 3.3 Add confidence scoring for country/city/region candidates.
- [x] 3.4 Mark ambiguous or low-confidence places as unresolved rather than forcing a match.
- [x] 3.5 Add tests for exact, alias-like, ambiguous, and unresolved geography cases.

## 4. Relationship materialization

- [x] 4.1 Define relationship types connecting organizations, persons, publications, datasets, projects, events, and concepts to geographic entities.
- [x] 4.2 Materialize organization `located_in` relations from resolved institution geography.
- [x] 4.3 Materialize publication `associated_with` geography from author affiliations.
- [x] 4.4 Materialize dataset `covers_region` relations when spatial coverage exists.
- [x] 4.5 Add relationship tests with provenance and confidence.

## 5. Analytics integration

- [x] 5.1 Update geographic analytics to prefer normalized geographic entity metadata.
- [x] 5.2 Keep existing affiliation text parsing as fallback.
- [x] 5.3 Add dashboard/API test proving normalized country codes drive geographic counts.
- [x] 5.4 Add future-ready contract for map visualizations without building the map UI yet.

## 6. Linked Data alignment

- [x] 6.1 Document mapping to schema.org Place.
- [x] 6.2 Document mapping to DCAT spatial coverage for datasets.
- [x] 6.3 Document mapping to EDM Place and BIBFRAME Place.
- [x] 6.4 Keep geometry fields compatible with future GeoSPARQL export.

## 7. Validation

- [x] 7.1 Run `npx openspec validate geographic-entity-semantic-layer --strict`.
- [x] 7.2 Run focused geographic analytics tests.
- [x] 7.3 Add codemap documentation for the geographic semantic layer.
