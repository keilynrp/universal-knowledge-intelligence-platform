## Context

Geographic semantics sit at the intersection of institutional affiliation, research outputs, datasets, projects, and stakeholder decisions. UKIP already extracts country-like signals from affiliations, but this is currently text-oriented and not a full semantic layer.

The target architecture is:

```
raw geography text / country code / affiliation
  -> geographic candidate
  -> reconciliation/geocoding
  -> canonical geographic entity
  -> relationships and evidence
  -> analytics, reports, linked-data export
```

## Goals / Non-Goals

**Goals:**
- Treat geographic entities as first-class semantic entities.
- Preserve geography provenance and confidence.
- Support hierarchy: address/campus -> city -> region -> country.
- Support identifiers: ISO, GeoNames, Wikidata, OpenStreetMap/Nominatim IDs where available.
- Support coordinates and optional geometry.
- Connect organizations, publications, datasets, projects, events, persons, and concepts to places.
- Align with Linked Data standards.

**Non-Goals:**
- Full GIS system or spatial database in the first pass.
- Real-time map UI.
- Paid geocoding providers.
- Automatic backfill of all historical records.
- Polygons for every place in the first pass.

## Canonical Geographic Entity

Suggested model:

```python
class GeographicEntity(BaseModel):
    id: str
    name: str
    type: Literal["country", "region", "city", "campus", "address", "spatial_area", "unknown"]
    aliases: list[str] = []
    country_code: str | None = None
    region_code: str | None = None
    geonames_id: str | None = None
    wikidata_id: str | None = None
    osm_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geometry: dict | None = None
    parent_id: str | None = None
    confidence: float | None = None
    provenance: dict = {}
```

## Relationship Contract

Examples:

- `organization located_in geographic_entity`
- `person affiliated_in geographic_entity`
- `publication associated_with geographic_entity`
- `dataset covers_region geographic_entity`
- `project funded_in geographic_entity`
- `event held_at geographic_entity`
- `concept prevalent_in geographic_entity`
- `geographic_entity contained_in geographic_entity`

Each relation should preserve:

- source field or provider
- evidence string/object
- confidence
- extraction method

## Standards Alignment

### ISO 3166

Use ISO country codes and, where possible, subdivision codes as stable compact identifiers.

### GeoNames

Use GeoNames IDs for city/region/place identifiers when available.

### Wikidata

Use Wikidata QIDs for multilingual aliases, hierarchy, and broad linked-data interoperability.

### schema.org Place

Expose a JSON-LD-compatible place shape for web interoperability.

### DCAT spatial coverage

Use for datasets and data products that describe or cover a geographic area.

### Europeana EDM Place

Use for cultural heritage / digital object contexts where place enriches an object or aggregation.

### BIBFRAME Place

Use for bibliographic place semantics such as publication place or geographic subject.

### GeoSPARQL

Keep geometry/properties compatible with future GeoSPARQL export, but do not require full implementation now.

## Reconciliation Strategy

Input signals:

- country code
- country name
- region/state/province
- city
- address
- institution country from OpenAlex/ROR
- free-text affiliation
- dataset spatial coverage
- imported geographic columns

Scoring signals:

- exact ISO code
- normalized country/city name
- alias match
- parent hierarchy match
- institution location context
- coordinate plausibility
- source reliability

## Persistence Strategy

Initial implementation can persist:

- normalized geographic entity metadata in `attributes_json` for source records
- relationship materialization in existing graph/relationship structures if available
- canonical geographic authority records if the authority model can represent places

Longer term, a dedicated table may be warranted for geographic entities and place relationships.

## Risks / Trade-offs

- **Risk: Geocoding false positives.** Mitigation: use confidence thresholds and preserve unresolved candidates.
- **Risk: Place hierarchy differs across standards.** Mitigation: store source identifiers and parent relations with provenance.
- **Risk: Overbuilding GIS too early.** Mitigation: start with identifiers, hierarchy, lat/lon, and evidence; defer geometry-heavy features.
- **Risk: Multilingual names and aliases.** Mitigation: Wikidata/GeoNames aliases and source-specific labels.

## Rollout Plan

1. Define geographic entity and relationship contracts.
2. Add helpers for ISO country normalization.
3. Add candidate extraction from affiliations and imported geographic columns.
4. Add reconciliation hooks for GeoNames/Wikidata/Nominatim later.
5. Update geographic analytics to prefer normalized geography.
6. Add linked-data export mapping in a later change.
