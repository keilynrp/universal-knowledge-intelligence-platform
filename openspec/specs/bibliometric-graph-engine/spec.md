## ADDED Requirements

### Requirement: Bibliometric graph engine declares relationship semantics
The system SHALL maintain a documented relationship taxonomy for scientometric graphs. Each derived edge SHALL include `relation_type`, `weight`, and JSON evidence in `notes` with at least: `algorithm`, `support_count`, `source_fields`, and `derived_by`.

#### Scenario: Derived relationship includes evidence
- **WHEN** the graph materializer creates a co-word, same-as, equivalent, or inferred related edge
- **THEN** the relationship `notes` field contains a JSON object with algorithm name, support count, source fields, and provenance

### Requirement: Concept co-occurrence network
The system SHALL derive `keyword-co-occurs-with` edges between concept nodes that co-occur in at least two records in the same import batch and domain. Edge weight SHALL be computed using association strength: `cooccurrence(i,j) / (occurrence(i) * occurrence(j))`, scaled into the existing 0-10 weight range.

#### Scenario: Repeated co-occurring concepts create a weighted edge
- **WHEN** two concepts appear together in two or more records in the same batch
- **THEN** the materializer creates one `keyword-co-occurs-with` edge between the concept nodes
- **AND** `notes.algorithm` is `association_strength`
- **AND** `notes.support_count` equals the number of records where the pair co-occurs

#### Scenario: Single co-occurrence is not enough
- **WHEN** two concepts appear together in only one record
- **THEN** no `keyword-co-occurs-with` edge is created

### Requirement: Document similarity from shared concepts
The system SHALL derive `related-to` edges between publication records that share two or more normalized concepts. Edge weight SHALL use Jaccard similarity over the normalized concept sets.

#### Scenario: Documents sharing concepts are linked
- **WHEN** two publications in a batch share at least two concepts
- **THEN** the materializer creates a `related-to` edge between the publications
- **AND** `notes.algorithm` is `concept_jaccard`
- **AND** `notes.evidence.shared_concepts` lists the shared concepts

### Requirement: Same-as links by stable identifiers
The system SHALL derive `same-as` edges between publication records that share a stable identifier such as DOI, OpenAlex ID, Scopus EID, or WoS accession number.

#### Scenario: Duplicate records with same DOI
- **WHEN** two records in the same tenant share the same DOI
- **THEN** the materializer creates a `same-as` relationship between the records
- **AND** the evidence identifies DOI as the matching field

### Requirement: Concept equivalence links
The system SHALL derive `equivalent-to` edges between concept nodes when a short acronym and an expanded phrase are both present in the same batch and the acronym matches the phrase initials.

#### Scenario: Acronym and phrase are equivalent
- **WHEN** concept nodes "AI" and "Artificial Intelligence" exist in the same batch
- **THEN** the materializer creates an `equivalent-to` edge between those concept nodes
- **AND** `notes.algorithm` is `acronym_initials`

### Requirement: Incremental materialization remains idempotent
The system SHALL NOT create duplicate edges when materialization is run repeatedly for the same import batch.

#### Scenario: Re-running materialization is stable
- **WHEN** the same batch is materialized twice
- **THEN** the second run creates zero duplicate derived relationships for the same source, target, relation type, and batch marker

### Requirement: Graph engine consumes semantic signal relationship candidates
The bibliometric graph engine SHALL be allowed to persist relationship candidates emitted by the semantic keyword signal engine, but SHALL NOT own keyword opportunity scoring, LSI projection, long-tail classification, or external signal alignment.

#### Scenario: Semantic signal emits graph candidate
- **WHEN** the semantic keyword signal engine emits an `external-signal-for`, `derived-keyword`, `semantic-neighbor`, or `emerging-from` candidate
- **THEN** the graph engine may persist the relationship with evidence in `notes`
- **AND** the relationship evidence identifies the semantic keyword signal engine as the producing subsystem

#### Scenario: Graph materialization remains bibliometric
- **WHEN** the graph engine materializes a batch
- **THEN** it computes corpus graph relations such as co-word, same-as, related-to, equivalent-to, citation, author, journal, and identifier edges
- **AND** it does not fit LSI models or classify keyword opportunity tails directly
