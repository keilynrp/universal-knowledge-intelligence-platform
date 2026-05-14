## ADDED Requirements

### Requirement: Generalized pipeline payload
The `ProcessRequest` proto message SHALL support pipeline-specific input via a `oneof payload` field, alongside the existing `publications` repeated field for backward compatibility.

#### Scenario: Import pipeline uses publications field
- **WHEN** a `ProcessRequest` is sent with pipeline="graph_materialization" and publications filled
- **THEN** the engine SHALL process it exactly as before (no breaking change)

#### Scenario: Compute pipeline uses typed payload
- **WHEN** a `ProcessRequest` is sent with pipeline="compute_authority" and payload set to `AuthorityRequest`
- **THEN** the engine SHALL deserialize the typed payload and pass it to the authority pipeline

### Requirement: AuthorityRequest message
The proto SHALL define an `AuthorityRequest` message with fields: field_name (string), values (repeated string), entity_type (string), context_affiliation (optional string), context_orcid_hint (optional string), context_doi (optional string), context_year (optional int32).

#### Scenario: Authority request with full context
- **WHEN** an `AuthorityRequest` is sent with all context fields populated
- **THEN** the engine SHALL use all context in scoring

### Requirement: AuthorityResponse message
The proto SHALL define an `AuthorityResponse` message containing repeated `AuthorityCandidateGroup` (one per input value), each with repeated `AuthorityCandidate` (source, id, label, confidence, score_breakdown map, resolution_status, merged_sources).

#### Scenario: Response structure
- **WHEN** an authority pipeline completes
- **THEN** the `ProcessResponse.result` SHALL contain serialized `AuthorityResponse` in an extended result field

### Requirement: AnalyticsRequest message
The proto SHALL define an `AnalyticsRequest` message with fields: domain_id (string), mode (string: "topics", "cooccurrence", "clusters", "correlation"), limit (int32), field_filters (repeated string).

#### Scenario: Topic analysis request
- **WHEN** an `AnalyticsRequest` is sent with mode="topics" and limit=20
- **THEN** the engine SHALL return the top 20 topics for the domain

### Requirement: DisambiguationRequest message
The proto SHALL define a `DisambiguationRequest` message with fields: field_name (string), values (repeated string), similarity_threshold (float, default 0.85).

#### Scenario: Disambiguation with custom threshold
- **WHEN** a `DisambiguationRequest` is sent with similarity_threshold=0.90
- **THEN** the engine SHALL use 0.90 as the clustering threshold

### Requirement: NormalizationRequest message
The proto SHALL define a `NormalizationRequest` message with fields: values (repeated string), mode (string: "unicode", "name_variants", "rules"), rules (repeated NormalizationRule with pattern and replacement fields).

#### Scenario: Normalization with rules
- **WHEN** a `NormalizationRequest` is sent with mode="rules" and a list of rules
- **THEN** the engine SHALL apply rules in order and return normalized values

### Requirement: ConnectorRequest message
The proto SHALL define a `ConnectorRequest` message with fields: source (string: "openalex", "crossref", "pubmed"), query_type (string: "doi", "title", "pmid", "search"), queries (repeated string).

#### Scenario: Batch DOI lookup
- **WHEN** a `ConnectorRequest` is sent with source="crossref", query_type="doi", queries=["10.1234/abc", "10.5678/def"]
- **THEN** the engine SHALL resolve both DOIs and return Publication messages

### Requirement: ListJobs RPC
The proto SHALL define a `ListJobsRequest` (pipeline_filter optional string, status_filter optional string, limit int32) and `ListJobsResponse` (repeated JobSummary with job_id, pipeline, status, progress, created_at, completed_at).

#### Scenario: List all jobs
- **WHEN** `ListJobs` is called with no filters
- **THEN** the engine SHALL return recent jobs from the persistent store

### Requirement: Backward compatibility
All existing RPCs (ProcessSync, ProcessAsync, GetJobStatus, StreamProgress, Health) SHALL continue to work unchanged with existing proto messages.

#### Scenario: Existing client unchanged
- **WHEN** the Python EngineClient sends a `ProcessRequest` with only `publications` filled (no oneof payload)
- **THEN** the engine SHALL process it identically to the current behavior
