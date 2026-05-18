## ADDED Requirements

### Requirement: H-index computation
The system SHALL compute the h-index for an author by collecting citation counts of all entities linked to that author's authority record, sorting descending, and finding the largest h such that at least h entities have h or more citations.

#### Scenario: Compute h-index for author with mixed citations
- **WHEN** an author has entities with citation counts [50, 30, 20, 10, 5, 1]
- **THEN** the system SHALL return h-index = 4 (4 papers with >= 4 citations)

#### Scenario: Author with no citations
- **WHEN** all entities linked to an author have `enrichment_citation_count = 0` or NULL
- **THEN** the system SHALL return h-index = 0

#### Scenario: Author not found
- **WHEN** the requested author has no confirmed authority record
- **THEN** the system SHALL return HTTP 404

### Requirement: Author productivity metrics
The system SHALL compute per-author productivity metrics including total publications, total citations, average citations per publication, and publications per year timeline.

#### Scenario: Compute productivity for a known author
- **WHEN** an authenticated user requests metrics for an author by authority record ID
- **THEN** the system SHALL return `total_publications`, `total_citations`, `avg_citations`, `h_index`, and `publications_per_year` (dict of year→count)

#### Scenario: Publications per year timeline
- **WHEN** an author has publications spanning 2018-2024
- **THEN** `publications_per_year` SHALL include entries for each year with at least one publication, with the count of publications in that year

### Requirement: Top authors ranking endpoint
The system SHALL expose `GET /analyzers/authors/{domain_id}` returning a ranked list of authors with their productivity metrics.

#### Scenario: Rank by h-index
- **WHEN** an authenticated user requests `GET /analyzers/authors/{domain_id}?sort_by=h_index&limit=20`
- **THEN** the system SHALL return the top 20 authors ranked by h-index descending, each with `canonical_label`, `h_index`, `total_publications`, `total_citations`

#### Scenario: Rank by total publications
- **WHEN** `sort_by=total_publications` is specified
- **THEN** the system SHALL rank authors by publication count descending

#### Scenario: Domain with no authority records
- **WHEN** the domain has no confirmed authority records with `field_name='author'`
- **THEN** the system SHALL return an empty `authors` array with `total_analyzed: 0`

### Requirement: Single author detail endpoint
The system SHALL expose `GET /analyzers/authors/{domain_id}/{record_id}` returning full productivity detail for a single author.

#### Scenario: Retrieve author detail
- **WHEN** an authenticated user requests detail for a valid authority record ID
- **THEN** the system SHALL return the full productivity metrics including `h_index`, `total_publications`, `total_citations`, `avg_citations`, `publications_per_year`, and a list of the author's top-cited entities (up to 10)

#### Scenario: Record belongs to different domain
- **WHEN** the authority record exists but its linked entities are not in the requested domain
- **THEN** the system SHALL return HTTP 404
