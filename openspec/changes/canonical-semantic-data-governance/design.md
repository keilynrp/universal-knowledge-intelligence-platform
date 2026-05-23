## Context

UKIP is becoming an agnostic semantic engine. Its value does not come from supporting one connector, one domain, or one schema. Its value comes from accepting heterogeneous sources, understanding their structure, proposing mappings, preserving source evidence, resolving authority identities, enriching with reliable external evidence, and producing intelligence outputs that stakeholders can trust.

Current active specs already point in this direction:

- `entity-provenance-layering` separates original ingestion, UKIP normalized identity, external enrichment, and authority/audit.
- `scientific-affiliation-normalization` preserves structured author-institution relationships from OpenAlex and similar sources.
- `institution-affiliation-reconciliation` resolves institutions against ROR and secondary authorities.
- `geographic-entity-semantic-layer` introduces first-class place semantics and linked-data geography.
- `research-stakeholder-executive-demo` exposes these capabilities to research stakeholders.

This spec defines the governance layer above them.

## Governance Baseline

### Active data-model spec inventory

| Spec | Governance role | Primary canonical concern | Required governance reference |
| --- | --- | --- | --- |
| `canonical-semantic-data-governance` | `governing` | Cross-cutting canonical lifecycle, boundaries, and linked-data alignment | Root data governance layer |
| `domain-agnostic-core-cleanup` | `governing` / `presentation` | Domain-neutral core terminology and compatibility containment | Must preserve canonical vocabulary and adapter boundaries |
| `entity-provenance-layering` | `presentation` / `canonical-specialization` | Source, normalized, enrichment, authority, and audit field grouping | Must use canonical layer names and field-state semantics |
| `scientific-affiliation-normalization` | `source-adapter` / `canonical-specialization` | Structured author, affiliation, institution, and ROR-ready metadata | Must preserve original source affiliation evidence separately from canonical candidates |
| `institution-affiliation-reconciliation` | `authority-resolver` | Institution candidates, ROR/OpenAlex/Wikidata identity, scoring, and review | Must not overwrite source affiliation text or enrichment observations |
| `geographic-entity-semantic-layer` | `canonical-specialization` / `authority-resolver` | Places, geographic identifiers, confidence, relationships, and linked-data geography | Must align place semantics to canonical provenance and linked-data rules |
| `authority-enrichment-bridge` | `authority-resolver` / `enrichment-provider` | Candidate extraction and promotion from source plus enrichment evidence | Must keep extraction, review, authority decision, and canonical promotion distinct |
| `research-stakeholder-executive-demo` | `presentation` | Stakeholder-facing decision readouts and evidence traceability | Must explain whether claims come from source, canonical, enrichment, authority, or linked-data layers |
| `rag-skill-orchestration` | `presentation` / `enrichment-provider` | Skill-assisted RAG outputs over governed evidence | Must keep AI outputs read-only unless a governed review/promotion path exists |

### Acceptance criteria for future data-model specs

Every future data-model spec SHALL declare:

- Governance role: `governing`, `canonical-specialization`, `source-adapter`, `authority-resolver`, `enrichment-provider`, or `presentation`.
- Affected canonical entities, relationships, identifiers, observations, or field states.
- Source payloads, imported fields, or provider records consumed.
- Provenance boundary: original source, normalized UKIP identity, enrichment, authority, audit, or presentation.
- Confidence and review rules, including when human review is required.
- Linked-data alignment, if outputs may be exported or used for interoperability.
- Downstream consumers affected: analytics, graph, reports, RAG, dashboards, or APIs.
- Backward-compatibility and migration expectations.

### Canonical semantic lifecycle

```mermaid
flowchart LR
  A["Source payload or file"] --> B["Source profile"]
  B --> C["Mapping suggestion"]
  C --> D["Reviewed mapping decision"]
  D --> E["Canonical entity / relationship candidate"]
  E --> F["Authority resolution"]
  E --> G["Evidence-based enrichment"]
  F --> H["Canonical promotion with provenance"]
  G --> I["Enrichment observation"]
  H --> J["Analytics / graph / reports / RAG"]
  I --> J
  J --> K["Stakeholder intelligence with evidence"]
```

Lifecycle rules:

- Source profiling precedes mapping for arbitrary or unfamiliar sources.
- Mapping suggestions are reviewable artifacts, not silent canonical truth.
- Canonical identity is promoted only by governed source mapping, authority decision, or explicit review rule.
- Enrichment observations can support confidence and narrative, but remain distinguishable from authority decisions.
- Presentation layers may summarize canonical and enrichment evidence, but must not erase provenance.

## Goals / Non-Goals

**Goals:**
- Define the canonical semantic governance contract for all data-model specs.
- Require subordinate specs to declare their role and dependencies.
- Establish the lifecycle from arbitrary source to canonical model to authority/enrichment to linked-data/reporting outputs.
- Make source profiling and mapping suggestions first-class concepts.
- Preserve strict boundaries between source data, canonical identity, authority resolution, and enrichment.
- Align future exports with BIBFRAME, Europeana EDM, schema.org, JSON-LD, and other linked-data standards.

**Non-Goals:**
- Implement the full canonical database schema immediately.
- Replace existing entity storage in one migration.
- Pick a single universal ontology as UKIP's internal model.
- Require all ingested data to be bibliographic or scientific.
- Treat enrichment provider payloads as canonical truth.

## Governance Layers

### 1. Source profiling

The source profiler inspects arbitrary ingested data before mapping. It identifies:

- Field names and value distributions
- Candidate identifiers
- Candidate entity types
- Candidate relationship fields
- Candidate temporal, geographic, institutional, person, publication, dataset, and concept fields
- Field quality, sparsity, ambiguity, and sample evidence

### 2. Mapping suggestions

Mapping suggestions translate profiled source fields into UKIP canonical candidates. They are recommendations, not silent transformations.

Each suggestion should include:

- Source field
- Proposed canonical field or entity role
- Confidence
- Evidence samples
- Transformation rule
- Conflict or ambiguity notes
- Whether human review is required

### 3. UKIP canonical data model

The canonical model is UKIP's internal semantic contract. It should be:

- Domain-agnostic at the core
- Extensible by subordinate domain specs
- Strict about provenance and field state
- Able to represent entities, relationships, identifiers, measures, temporal coverage, geographic coverage, evidence, authority links, and enrichment observations

### 4. Authority resolution

Authority resolution links canonical candidates to trusted registries. Examples include:

- ROR for institutions
- ORCID for persons
- DOI/Crossref/DataCite for scholarly objects and datasets
- OpenAlex for scholarly graph context
- GeoNames/Wikidata/ISO/OSM for places
- BIBFRAME/LC-compatible authorities for bibliographic and cultural heritage contexts

Authority resolution can strengthen canonical identity, but it must preserve provenance and confidence.

### 5. Evidence-based enrichment

Enrichment adds external observations. It must not overwrite canonical source truth unless a governed rule permits it.

Examples:

- Citation counts
- Concepts/topics
- Institutional affiliations
- Geographic coordinates
- Organization metadata
- Publication venues
- Funding and project context

Enrichment must remain distinguishable from original ingestion and authority resolution.

### 6. Linked-data alignment

Linked-data alignment maps governed canonical semantics into interoperable external models:

- BIBFRAME for bibliographic/resource description
- Europeana EDM for cultural heritage aggregation
- schema.org for web-scale structured data
- JSON-LD as a pragmatic serialization layer
- DCAT for datasets and spatial coverage
- GeoSPARQL for advanced future geospatial relationships

### 7. Executive intelligence

Executive intelligence and reports consume the governed semantic layer. They should not infer strategic claims directly from raw provider payloads when canonical, authority-resolved, or evidence-enriched data is available.

## Decisions

### D1: This spec governs all data-model evolution

**Decision:** Any spec that introduces or modifies data-model semantics SHALL declare its relationship to `canonical-semantic-data-governance`.

**Rationale:** UKIP needs controlled extensibility. Domain specs should enrich the model, not fork it.

### D2: UKIP uses a canonical semantic model, not a single imported ontology

**Decision:** UKIP SHALL maintain its own canonical model and align to external standards through explicit mappings.

**Rationale:** BIBFRAME, EDM, schema.org, DCAT, GeoSPARQL, OpenAlex, Crossref, ROR, and other models solve different problems. UKIP needs interoperability without surrendering its internal governance.

### D3: Source profiling precedes mapping

**Decision:** Arbitrary source ingestion SHALL be profiled before canonical mapping suggestions are accepted.

**Rationale:** A source-agnostic engine cannot safely map unfamiliar structures without field evidence, sample values, sparsity, and ambiguity analysis.

### D4: Mapping suggestions are reviewable artifacts

**Decision:** Mapping suggestions SHALL be stored or exposed as reviewable artifacts when confidence is below the governed acceptance threshold.

**Rationale:** Low-confidence mappings can damage trust across enrichment, linked-data export, and executive reporting.

### D5: Enrichment does not equal authority

**Decision:** Evidence-based enrichment SHALL be modeled separately from authority resolution.

**Rationale:** A provider can contribute useful observations without being the canonical authority for identity.

### D6: Linked-data output is generated from canonical semantics

**Decision:** JSON-LD/RDF-compatible outputs SHALL be generated from UKIP canonical semantics and declared alignments, not directly from raw source payloads.

**Rationale:** This keeps exports stable even when source structures or providers change.

## Subordination Rules

Data-model specs SHALL identify one or more roles:

- `governing`: defines cross-cutting data governance rules.
- `canonical-specialization`: extends the canonical model for a domain or entity family.
- `source-adapter`: maps a provider or file/source type into canonical candidates.
- `authority-resolver`: resolves canonical candidates against trusted registries.
- `enrichment-provider`: adds external evidence while preserving provenance.
- `presentation`: renders governed data for users or reports.

Subordinate specs SHALL state:

- Which canonical entities or relationships they affect.
- Which source fields or provider payloads they consume.
- Which authority registries they trust.
- Which enrichment observations they add.
- Which linked-data standards they align to.
- Which provenance and confidence rules apply.

## Open Questions

- What is the minimum canonical entity envelope required before implementing source profiling UI?
- Should mapping suggestions be persisted as first-class records or derived from import jobs?
- What confidence thresholds should trigger human review?
- How should UKIP version canonical model changes over time?
- Should linked-data alignment initially emit JSON-LD only, with RDF/TTL later?

## Rollout Plan

1. Establish this spec as the governing change.
2. Update active subordinate specs to reference this governance layer in their implementation tasks.
3. Define canonical entity and relationship envelopes.
4. Implement source profiling contracts for tabular/file/API imports.
5. Implement mapping suggestion artifacts and review states.
6. Connect authority resolution and enrichment outputs to canonical provenance layers.
7. Generate linked-data exports from canonical semantics.
8. Surface governed canonical/evidence distinctions in executive intelligence and reports.
