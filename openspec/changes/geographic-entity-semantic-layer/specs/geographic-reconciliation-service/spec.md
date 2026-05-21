## ADDED Requirements

### Requirement: UKIP reconciles raw geography into geographic entities
UKIP SHALL provide reconciliation logic that converts raw geography strings, country codes, coordinates, and affiliation-derived location hints into canonical geographic entities when confidence is sufficient.

#### Scenario: ISO country code is provided
- **WHEN** a source provides a valid ISO country code
- **THEN** UKIP resolves it deterministically to a country geographic entity

#### Scenario: Free-text country is provided
- **WHEN** a source provides a country name
- **THEN** UKIP normalizes it to a country geographic entity when unambiguous

#### Scenario: Ambiguous place is provided
- **WHEN** a place name maps to multiple plausible entities
- **THEN** UKIP marks the candidate as unresolved or review-needed instead of forcing a match

### Requirement: Reconciliation preserves evidence
Geographic reconciliation results SHALL preserve source evidence and confidence.

#### Scenario: Place is resolved from affiliation
- **WHEN** country/city is extracted from an affiliation
- **THEN** the resulting geographic entity or candidate includes the original affiliation evidence and extraction method
