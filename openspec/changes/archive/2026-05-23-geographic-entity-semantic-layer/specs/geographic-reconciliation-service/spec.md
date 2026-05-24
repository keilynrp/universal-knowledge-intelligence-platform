## ADDED Requirements

### Requirement: UKIP reconciles raw geography into geographic entities
UKIP SHALL provide reconciliation logic that converts raw geography strings, country codes, coordinates, and affiliation-derived location hints into canonical geographic entities when confidence is sufficient.

#### Scenario: ISO country code is provided
- **WHEN** a source provides a valid ISO country code
- **THEN** UKIP resolves it deterministically to a country geographic entity with confidence 1.0

#### Scenario: Free-text country is provided
- **WHEN** a source provides a country name
- **THEN** UKIP normalizes it to a country geographic entity when unambiguous

#### Scenario: Ambiguous place is provided
- **WHEN** a place name maps to multiple plausible entities
- **THEN** UKIP marks the candidate as unresolved or review-needed instead of forcing a match
- **AND** all plausible candidates are preserved with their respective confidence scores

#### Scenario: Low-confidence candidate is not promoted
- **WHEN** reconciliation produces only candidates below the governed confidence threshold
- **THEN** UKIP does not create a canonical geographic entity
- **AND** the candidates remain available for manual review or future reconciliation

### Requirement: Reconciliation preserves evidence
Geographic reconciliation results SHALL preserve source evidence and confidence.

#### Scenario: Place is resolved from affiliation
- **WHEN** country/city is extracted from an affiliation
- **THEN** the resulting geographic entity or candidate includes the original affiliation evidence and extraction method

#### Scenario: Place is resolved from imported column
- **WHEN** a geographic entity is derived from an imported column named country, city, region, or similar
- **THEN** the reconciliation result records the source column name, original value, and extraction method

#### Scenario: Place is resolved from dataset spatial coverage
- **WHEN** a geographic entity is derived from a dataset spatial coverage field
- **THEN** the reconciliation result records the spatial coverage value and extraction method

### Requirement: Geographic candidates are extracted from structured affiliations
UKIP SHALL extract geographic candidates from structured affiliation data.

#### Scenario: Country is extracted from parsed affiliation
- **WHEN** a structured affiliation includes a country field or country-like token
- **THEN** UKIP extracts a geographic candidate with type `country` and the raw text as evidence

#### Scenario: City is extracted from parsed affiliation
- **WHEN** a structured affiliation includes a city field or city-like token
- **THEN** UKIP extracts a geographic candidate with type `city` and the raw text as evidence

#### Scenario: Affiliation without geography produces no candidate
- **WHEN** a structured affiliation contains no recognizable geographic tokens
- **THEN** UKIP does not produce a geographic candidate from that affiliation

### Requirement: Geographic candidates are extracted from imported columns
UKIP SHALL extract geographic candidates from imported columns with geographic semantics.

#### Scenario: Column named country produces candidates
- **WHEN** an imported dataset has a column named "country", "Country", or "country_code"
- **THEN** UKIP extracts geographic candidates from each non-empty cell value

#### Scenario: Column named city or region produces candidates
- **WHEN** an imported dataset has a column named "city", "region", "state", or "province"
- **THEN** UKIP extracts geographic candidates with the appropriate type

#### Scenario: Latitude and longitude columns produce coordinate candidates
- **WHEN** an imported dataset has columns named "latitude"/"longitude" or "lat"/"lon"
- **THEN** UKIP extracts coordinate pairs and associates them with geographic candidates when a place name is also available

### Requirement: ISO country normalization is the first reconciliation path
UKIP SHALL implement ISO 3166-1 alpha-2 country normalization as the primary deterministic reconciliation step.

#### Scenario: Valid ISO code resolves deterministically
- **WHEN** a candidate provides a valid ISO 3166-1 alpha-2 code
- **THEN** reconciliation resolves it to the corresponding country entity with confidence 1.0

#### Scenario: Common country name resolves to ISO code
- **WHEN** a candidate provides a well-known country name (e.g., "United States", "Germany", "Japan")
- **THEN** normalization maps it to the correct ISO code deterministically

#### Scenario: Variant country name resolves via alias
- **WHEN** a candidate provides a variant name (e.g., "USA", "U.S.A.", "Estados Unidos", "Deutschland")
- **THEN** normalization maps it to the correct ISO code via alias matching

### Requirement: Place name normalization supports alias-ready matching
UKIP SHALL normalize place names using case folding, diacritic stripping, and alias lookup.

#### Scenario: Case-insensitive match succeeds
- **WHEN** a candidate provides "united kingdom" or "UNITED KINGDOM"
- **THEN** normalization matches it to the same entity as "United Kingdom"

#### Scenario: Diacritic-insensitive match succeeds
- **WHEN** a candidate provides "Zurich" or "Zuerich"
- **THEN** normalization matches it to the same entity as the canonical Zurich entry

### Requirement: Confidence scoring reflects reconciliation quality
UKIP SHALL assign confidence scores to geographic reconciliation results based on the quality and specificity of evidence.

#### Scenario: Exact ISO code match has highest confidence
- **WHEN** reconciliation uses a valid ISO code
- **THEN** the confidence score is 1.0

#### Scenario: Exact name match has high confidence
- **WHEN** reconciliation uses an exact normalized name match
- **THEN** the confidence score is at least 0.9

#### Scenario: Alias match has moderate confidence
- **WHEN** reconciliation uses an alias or variant name match
- **THEN** the confidence score is between 0.7 and 0.9

#### Scenario: Ambiguous match has low confidence
- **WHEN** reconciliation cannot determine a unique match
- **THEN** each candidate receives a confidence score below 0.7
- **AND** the candidates are marked as unresolved

### Requirement: Geographic reconciliation tests cover representative cases
UKIP SHALL include tests for exact, alias, ambiguous, and unresolved geography reconciliation.

#### Scenario: Test verifies exact ISO resolution
- **WHEN** a test provides ISO code "US"
- **THEN** reconciliation returns a country entity for the United States with confidence 1.0

#### Scenario: Test verifies alias resolution
- **WHEN** a test provides "Deutschland"
- **THEN** reconciliation returns a country entity for Germany

#### Scenario: Test verifies ambiguous resolution
- **WHEN** a test provides "Georgia" without additional context
- **THEN** reconciliation returns multiple candidates (country vs. US state) marked as unresolved

#### Scenario: Test verifies unresolvable input
- **WHEN** a test provides a nonsensical geography string
- **THEN** reconciliation returns no candidates or a single candidate with confidence below the threshold
