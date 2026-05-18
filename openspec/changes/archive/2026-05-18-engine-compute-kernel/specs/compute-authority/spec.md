## ADDED Requirements

### Requirement: Authority resolution pipeline
The engine SHALL provide a `compute_authority` pipeline that accepts a list of entity field values and resolves them against authority sources, producing scored candidates with deduplication.

#### Scenario: Resolve a person name against multiple sources
- **WHEN** the pipeline receives a request with field_name="author", values=["J. Smith", "John Smith"], and entity_type="person"
- **THEN** the engine SHALL return a list of authority candidates per input value, each with authority_source, authority_id, canonical_label, confidence score, and score_breakdown

#### Scenario: Cross-source candidate deduplication
- **WHEN** two authority sources return candidates for the same real-world entity (e.g., Wikidata Q12345 and ORCID 0000-0001-...)
- **THEN** the engine SHALL merge them into a single candidate with merged_sources array and the highest confidence score, using token-sort similarity >= 92 as the merge threshold

### Requirement: Weighted scoring engine
The engine SHALL implement the same weighted scoring formula as `backend/authority/scoring.py`: 0.35 identifiers + 0.25 name + 0.20 affiliation + 0.10 reserved + 0.10 reserved, with dynamic weight renormalization when context fields are absent.

#### Scenario: Score with full context
- **WHEN** a candidate is scored with identifier match, name similarity, and affiliation match all available
- **THEN** the total score SHALL be the weighted sum using the standard weights, normalized to a 0.0-1.0 range

#### Scenario: Score with missing context
- **WHEN** affiliation context is not provided in the request
- **THEN** the engine SHALL renormalize the remaining weights so the maximum possible score is still 1.0

### Requirement: Fuzzy name matching
The engine SHALL implement fuzzy string matching using Jaro-Winkler similarity and token-sort-ratio (sorted token normalized Levenshtein) for name comparison.

#### Scenario: Token-sort-ratio match
- **WHEN** comparing "Smith, John A." and "John A. Smith"
- **THEN** the token-sort-ratio SHALL be >= 0.95 (near-identical after token sorting)

#### Scenario: Diacritic-insensitive matching
- **WHEN** comparing "Muller" and "Mueller" or "Muller" and "Muller" (with umlaut)
- **THEN** the engine SHALL normalize diacritics before comparison using NFD decomposition and ASCII folding

### Requirement: Resolution status thresholds
The engine SHALL classify candidates using the same thresholds as the Python implementation: exact_match >= 0.85, probable_match >= 0.65, ambiguous >= 0.45, unresolved < 0.45.

#### Scenario: Candidate classified as exact match
- **WHEN** a candidate scores 0.90
- **THEN** its resolution_status SHALL be "exact_match"

#### Scenario: Candidate classified as ambiguous
- **WHEN** a candidate scores 0.50
- **THEN** its resolution_status SHALL be "ambiguous"

### Requirement: Python fallback
The Python `backend/authority/resolver.py` SHALL delegate to the engine's `compute_authority` pipeline when the engine is available, and fall back to the existing Python ThreadPoolExecutor implementation when it is not.

#### Scenario: Engine available
- **WHEN** `EngineClient.health()` returns True
- **THEN** authority resolution SHALL call `EngineClient.process_sync(pipeline="compute_authority", ...)` and map the proto response to `AuthorityCandidate` objects

#### Scenario: Engine unavailable
- **WHEN** `EngineClient.health()` returns False
- **THEN** authority resolution SHALL use the existing Python resolver without error, logging a warning
