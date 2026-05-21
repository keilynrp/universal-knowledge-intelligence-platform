## 1. Governance baseline

- [ ] 1.1 Inventory active data-model specs and classify each as governing, canonical-specialization, source-adapter, authority-resolver, enrichment-provider, or presentation.
- [ ] 1.2 Add governance references to subordinate specs where needed.
- [ ] 1.3 Define acceptance criteria for future data-model specs.
- [ ] 1.4 Document canonical semantic lifecycle from source profiling to executive intelligence.

## 2. Source profiling contract

- [ ] 2.1 Define source profile artifact shape for tabular, API, connector, and demo imports.
- [ ] 2.2 Capture field names, inferred types, sparsity, sample values, value distributions, and candidate identifiers.
- [ ] 2.3 Detect candidate entity roles such as person, organization, publication, dataset, place, concept, project, event, and grant.
- [ ] 2.4 Add confidence and ambiguity indicators to profiling output.
- [ ] 2.5 Add tests for representative CSV/API/OpenAlex/Crossref-style payload profiling.

## 3. Mapping suggestion contract

- [ ] 3.1 Define mapping suggestion artifact with source field, target canonical field/entity role, confidence, evidence samples, transformation rule, and review state.
- [ ] 3.2 Add governed review thresholds for low-confidence or conflicting mappings.
- [ ] 3.3 Ensure mapping suggestions preserve original source field names and values.
- [ ] 3.4 Add mapping conflict handling for duplicate identifiers, ambiguous entity types, and mixed source fields.
- [ ] 3.5 Add tests for accepted, rejected, and review-required mapping suggestions.

## 4. Canonical model governance

- [ ] 4.1 Define canonical entity envelope with identity, labels, type, domain, identifiers, provenance, confidence, and field states.
- [ ] 4.2 Define canonical relationship envelope with subject, predicate, object, evidence, provenance, confidence, and temporal/spatial context.
- [ ] 4.3 Define canonical observation/enrichment envelope for externally sourced facts.
- [ ] 4.4 Define authority link envelope for registry-backed identity resolution.
- [ ] 4.5 Add versioning strategy for canonical model changes.

## 5. Authority and enrichment boundaries

- [ ] 5.1 Document authority resolution rules separately from enrichment rules.
- [ ] 5.2 Ensure enrichment provider data cannot overwrite canonical identity without a governed rule.
- [ ] 5.3 Define confidence aggregation rules across source evidence, authority matches, and enrichment observations.
- [ ] 5.4 Add tests proving original source, canonical identity, authority link, and enrichment observation remain distinguishable.

## 6. Linked-data governance

- [ ] 6.1 Define JSON-LD context generation strategy for canonical entities and relationships.
- [ ] 6.2 Map bibliographic/resource entities to BIBFRAME-compatible terms where applicable.
- [ ] 6.3 Map cultural heritage/resource aggregation entities to Europeana EDM-compatible terms where applicable.
- [ ] 6.4 Map general entities and places to schema.org-compatible terms where applicable.
- [ ] 6.5 Map datasets and spatial coverage to DCAT-compatible terms where applicable.
- [ ] 6.6 Define future GeoSPARQL alignment path for geospatial relationships.

## 7. Executive intelligence integration

- [ ] 7.1 Ensure dashboards and reports prefer canonical, authority-resolved, and evidence-enriched data over raw provider payloads.
- [ ] 7.2 Add provenance explanations for strategic claims in executive intelligence outputs.
- [ ] 7.3 Add report sections that distinguish source evidence, authority resolution, enrichment observations, and linked-data alignment.
- [ ] 7.4 Add tests for report claims generated from governed canonical data.

## 8. Validation

- [ ] 8.1 Run `npx openspec validate canonical-semantic-data-governance --strict`.
- [ ] 8.2 Run `npx openspec list` and confirm subordinate active specs remain visible.
- [ ] 8.3 Review spec consistency against `entity-provenance-layering`, `scientific-affiliation-normalization`, `institution-affiliation-reconciliation`, and `geographic-entity-semantic-layer`.
