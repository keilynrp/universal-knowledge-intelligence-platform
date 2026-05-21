## ADDED Requirements

### Requirement: ROR adapter supports lookup by identifier
The ROR adapter SHALL support lookup by normalized ROR identifier.

#### Scenario: ROR URL is provided
- **WHEN** the adapter receives `https://ror.org/03yrm5c26`
- **THEN** it normalizes the identifier and queries the corresponding ROR record

#### Scenario: Bare ROR ID is provided
- **WHEN** the adapter receives `03yrm5c26`
- **THEN** it treats it as the same organization identifier as the equivalent ROR URL

### Requirement: ROR adapter supports search by name and country
The ROR adapter SHALL support candidate search using institution name and optional country.

#### Scenario: Name and country are provided
- **WHEN** the adapter searches for an institution name with a country code
- **THEN** it returns candidate organizations with names, aliases, country, type, links, and external IDs

#### Scenario: ROR API is unavailable
- **WHEN** the ROR API request fails
- **THEN** the adapter returns a controlled error result and does not crash the reconciliation workflow
