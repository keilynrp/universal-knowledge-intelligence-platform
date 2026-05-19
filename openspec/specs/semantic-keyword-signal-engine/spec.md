## ADDED Requirements

### Requirement: Semantic keyword signal engine owns keyword opportunity analysis
The system SHALL provide a dedicated semantic keyword signal engine for extracting, classifying, and scoring keywords from internal corpus text and external attention evidence. This engine SHALL be separate from the bibliometric graph engine, but MAY emit graph relationships consumed by the graph layer.

#### Scenario: Separate semantic signal responsibility
- **WHEN** the system extracts long-tail keywords, derivative keywords, or external signal alignment
- **THEN** those outputs are produced by the semantic keyword signal engine
- **AND** bibliometric graph materialization remains responsible for corpus relationship construction

### Requirement: Internal corpus text sources
The semantic keyword signal engine SHALL build its internal corpus from title, abstract/resumen, keywords, enrichment_concepts, journal/source, document type, and normalized metadata fields when present.

#### Scenario: Entity with abstract and keywords
- **WHEN** an enriched record contains title, abstract, and keywords
- **THEN** the engine includes all three fields in the keyword extraction corpus
- **AND** records which only have title and enrichment_concepts still produce candidate keywords

### Requirement: N-gram extraction and normalization
The engine SHALL extract normalized 1-gram, 2-gram, 3-gram, and configurable 4-gram candidates using lowercase normalization, punctuation cleanup, stopword removal, and minimum token length filtering.

#### Scenario: Normalized keyword candidate
- **WHEN** the phrase "Open Educational Resources in Rural Universities" appears in an abstract
- **THEN** the engine may emit "open educational resources" and "rural universities"
- **AND** stopword-only candidates are discarded

### Requirement: Keyword tail classification
The engine SHALL classify keywords into `short_tail`, `mid_tail`, or `long_tail` using internal support count, document frequency ratio, TF-IDF score, and phrase length.

#### Scenario: Short-tail keyword
- **WHEN** a keyword appears in many records across the domain
- **THEN** it is classified as `short_tail`

#### Scenario: Long-tail keyword
- **WHEN** a multi-word keyword appears in a small number of records but has high TF-IDF or specificity
- **THEN** it is classified as `long_tail`

### Requirement: LSI topic projection
The engine SHALL support Latent Semantic Indexing using TF-IDF vectors plus truncated SVD to project records and keywords into latent topics. The implementation SHALL store the algorithm version and dimensionality used.

#### Scenario: LSI model metadata
- **WHEN** an LSI projection is generated
- **THEN** output metadata includes `algorithm: "tfidf_svd"`, `dimensions`, `fit_corpus_size`, and `model_version`

### Requirement: Derivative keyword detection
The engine SHALL identify derivative keywords from acronyms, normalized phrase variants, shared stems, high-similarity LSI neighbors, and high co-occurrence phrases.

#### Scenario: Acronym derivative
- **WHEN** "AI" and "Artificial Intelligence" occur in the same domain corpus
- **THEN** the engine marks "AI" as a derivative/equivalent keyword candidate for "Artificial Intelligence"

#### Scenario: LSI neighbor derivative
- **WHEN** two keywords are close in latent semantic space above a configured threshold
- **THEN** the engine may emit a `semantic_neighbor` relation candidate with similarity evidence

### Requirement: External signal alignment
The engine SHALL align internal keywords with external attention observations from news, policy, web, social, or configured external sources. Alignment SHALL use normalized exact match first, then phrase containment, then semantic similarity when available.

#### Scenario: Internal keyword with external support
- **WHEN** keyword "open science policy" appears internally and external attention observations mention that phrase
- **THEN** the engine emits an external signal score with internal support, external support, source types, and evidence snippets or source metadata

### Requirement: Opportunity score
The engine SHALL compute an opportunity score for each keyword using internal relevance, tail classification, growth velocity when temporal data exists, external signal strength, and confidence.

#### Scenario: Long-tail keyword with external demand
- **WHEN** a long-tail keyword has low internal support but strong external mentions
- **THEN** it receives a higher opportunity score than an unsupported long-tail keyword

### Requirement: Graph integration contract
The engine SHALL emit optional graph relationship candidates without directly owning graph materialization. Supported graph relation outputs SHALL include `derived-keyword`, `semantic-neighbor`, `external-signal-for`, and `emerging-from`.

#### Scenario: External signal relationship candidate
- **WHEN** a keyword has aligned external attention evidence
- **THEN** the engine may emit an `external-signal-for` candidate from the external signal node to the keyword/concept node
- **AND** the bibliometric graph engine or graph materializer is responsible for persisting the edge

### Requirement: Evidence-first persistence
Every persisted semantic keyword signal SHALL store evidence including source fields, support counts, scoring components, algorithm version, and generated timestamp.

#### Scenario: Persisted keyword signal is auditable
- **WHEN** a keyword signal is stored
- **THEN** it includes enough evidence to explain why it was classified and scored

### Requirement: Incremental updates
The engine SHALL support recalculating signals for an entity, import batch, domain, or external signal source without requiring a full rebuild unless requested.

#### Scenario: Enrichment completion triggers incremental update
- **WHEN** enrichment completes for a record with new abstract or keywords
- **THEN** the engine can update keyword candidates and affected signal scores for that record's domain
