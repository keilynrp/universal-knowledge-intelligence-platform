## ADDED Requirements

### Requirement: Data-model specs declare governance role
Every UKIP spec that introduces or modifies data-model semantics SHALL declare its governance role relative to the canonical semantic data layer.

#### Scenario: New domain model spec is proposed
- **WHEN** a spec adds a new domain entity family
- **THEN** it declares whether it is a `canonical-specialization`, `source-adapter`, `authority-resolver`, `enrichment-provider`, `presentation`, or `governing` spec
- **AND** it identifies the canonical entities, relationships, identifiers, provenance rules, and confidence rules it affects

#### Scenario: Source-specific adapter spec is proposed
- **WHEN** a spec maps a provider payload into UKIP
- **THEN** it declares the source payload fields it consumes
- **AND** it declares how those fields map into canonical candidates without overwriting canonical identity silently

### Requirement: Subordinate specs preserve canonical boundaries
Subordinate data-model specs SHALL preserve the distinction between original source data, UKIP canonical identity, authority resolution, evidence-based enrichment, linked-data alignment, and presentation.

#### Scenario: Enrichment provider adds a DOI
- **WHEN** an enrichment provider supplies a DOI for a record
- **THEN** UKIP stores it as an enrichment observation unless a governed authority or mapping rule promotes it to canonical identity

#### Scenario: Authority resolver matches an institution
- **WHEN** an institution candidate is matched to a ROR authority record
- **THEN** UKIP records the authority link with resolver source, confidence, and evidence
- **AND** it keeps the original source affiliation value available

### Requirement: Canonical semantics govern executive intelligence
Executive intelligence outputs SHALL prefer governed canonical semantics over raw source or provider payloads when available.

#### Scenario: Report uses institution affiliation data
- **WHEN** a report includes institutional collaboration claims
- **THEN** it uses canonical or authority-resolved institution relationships when available
- **AND** it exposes evidence/provenance for the claim

#### Scenario: Report uses geographic data
- **WHEN** a report includes geographic distribution claims
- **THEN** it uses normalized geographic entities when available
- **AND** falls back to raw geographic text only with explicit provenance or confidence limitations

### Requirement: Executive intelligence prefers governed canonical data
Dashboards, reports, and executive intelligence outputs SHALL prefer canonical, authority-resolved, enriched data over raw provider payloads when governed data is available.

#### Scenario: Dashboard displays institution collaboration network
- **WHEN** a dashboard renders an institutional collaboration network
- **THEN** it uses canonical organization identities with authority-resolved labels (e.g., ROR-linked names) when available
- **AND** falls back to raw source affiliation strings only when no canonical or authority-resolved identity exists
- **AND** visually distinguishes authority-resolved nodes from raw-source-only nodes

#### Scenario: Dashboard displays publication metrics by topic
- **WHEN** a dashboard displays publication counts grouped by topic or concept
- **THEN** it uses canonical concept identities rather than raw provider concept strings
- **AND** enrichment-derived concepts are included only when their provenance and confidence meet governed thresholds

#### Scenario: Report prefers enriched metadata over sparse source data
- **WHEN** a report generates claims about author affiliations, publication venues, or geographic distribution
- **THEN** it prefers enrichment-augmented canonical data that has passed governed promotion rules
- **AND** it does not silently mix raw provider values with canonical values in the same aggregation

### Requirement: Executive outputs include provenance explanations for strategic claims
Executive intelligence outputs SHALL provide provenance explanations that trace strategic claims back to their governing data layers.

#### Scenario: Report explains a collaboration strength claim
- **WHEN** a report states that Institution A and Institution B have a strong collaboration relationship
- **THEN** the report includes or links to provenance showing the co-authorship evidence count, the authority resolution status of both institutions, and the data sources contributing to the claim
- **AND** a user can inspect whether the claim relies on authority-resolved identities or raw affiliation string matching

#### Scenario: Report explains a geographic concentration claim
- **WHEN** a report claims that research output is concentrated in a specific geographic region
- **THEN** the report includes provenance showing whether geographic assignments derive from authority-resolved institutions (e.g., ROR country), enrichment observations, or raw source text
- **AND** confidence or coverage limitations are stated when fewer than a governed percentage of entities have authority-resolved geographic data

#### Scenario: Report explains a trending topic claim
- **WHEN** a report identifies a concept or topic as trending over a time period
- **THEN** the report provides provenance showing the concept source (canonical mapping, enrichment provider, or raw source field) and the aggregation method
- **AND** distinguishes between concepts derived from authority-aligned vocabularies and concepts derived from uncontrolled source text

### Requirement: Report sections distinguish evidence layers
Executive report sections SHALL clearly distinguish source evidence, authority resolution, enrichment observations, and linked-data alignment when presenting claims.

#### Scenario: Report section presents entity-level detail
- **WHEN** a report section presents detail about a specific entity (e.g., an author, institution, or work)
- **THEN** it separates the presentation into identifiable subsections or annotations for source-provided data, canonical identity, authority links, and enrichment observations
- **AND** each subsection identifies the data layer and its provenance

#### Scenario: Report section presents aggregate statistics
- **WHEN** a report section presents aggregate statistics (e.g., counts, distributions, averages)
- **THEN** it declares which data layer the aggregation draws from (canonical, authority-resolved, enriched, or mixed)
- **AND** when mixed layers are used, it states the composition (e.g., "78% authority-resolved, 22% raw source")

#### Scenario: Report section cites linked-data alignment
- **WHEN** a report section references external linked-data standards (e.g., schema.org types, BIBFRAME classes, Wikidata entities)
- **THEN** it cites the canonical-to-external alignment mapping used
- **AND** does not imply external standard compliance unless the alignment mapping has been governed and validated

### Requirement: Report claims generated from canonical data are testable
UKIP SHALL support verification that report claims are generated from governed canonical data with correct provenance chains.

#### Scenario: Claim cites correct canonical entity count
- **WHEN** a report claims "The corpus contains 1,247 works by authors affiliated with Institution X"
- **THEN** the claim is reproducible by querying the canonical entity layer filtered by authority-resolved affiliation for Institution X
- **AND** the count matches the governed canonical dataset, not a raw provider payload count that may include duplicates or unresolved affiliations

#### Scenario: Claim cites authority-resolved relationship
- **WHEN** a report claims "Author A is affiliated with Institution B (ROR: https://ror.org/...)"
- **THEN** the authority link between Author A and Institution B exists in the authority resolution layer with status confirmed or above the governed confidence threshold
- **AND** the ROR identifier in the claim matches the authority link record

#### Scenario: Claim derived from enrichment is labeled as such
- **WHEN** a report includes a claim that relies on enrichment-derived data (e.g., citation counts from OpenAlex, abstract keywords from Crossref)
- **THEN** the claim is annotated or labeled to indicate enrichment provenance
- **AND** the enrichment provider and observation timestamp are traceable from the claim

#### Scenario: Claim with insufficient governed data includes a caveat
- **WHEN** a report generates a claim but fewer than a governed percentage of contributing entities have canonical or authority-resolved data
- **THEN** the report includes a coverage caveat stating the percentage of entities with governed data versus raw source data
- **AND** the claim is not presented with the same confidence framing as claims backed by fully governed data
