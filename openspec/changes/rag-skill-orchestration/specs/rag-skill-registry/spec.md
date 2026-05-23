## ADDED Requirements

### Requirement: UKIP defines a governed skill registry for RAG
UKIP SHALL maintain a registry of approved skills that may be invoked by the RAG module.

#### Scenario: Skill is available to RAG
- **WHEN** the RAG module evaluates a skill for use
- **THEN** the skill definition includes `skill_id`, `version`, `description`, `input_schema`, `output_schema`, `allowed_evidence_types`, `governance_level`, timeout, and audit category
- **AND** the skill is enabled for the current tenant, domain, and feature policy

#### Scenario: Skill definition is invalid
- **WHEN** a skill lacks required metadata or schema contracts
- **THEN** UKIP SHALL reject the skill from the active registry
- **AND** SHALL NOT expose it to the RAG router

#### Scenario: Skill is disabled by feature flag or tenant policy
- **WHEN** a skill exists in the registry but is disabled for the current tenant or domain
- **THEN** the RAG router does not consider it for invocation
- **AND** the skill does not appear in available-skills queries for that scope

#### Scenario: Skill version is incompatible
- **WHEN** a skill definition specifies a version that is incompatible with the current execution runtime
- **THEN** UKIP rejects the skill from the active registry
- **AND** logs a warning with the incompatibility reason

### Requirement: Skill registry separates advisory skills from governed candidate-producing skills
UKIP SHALL classify skills by governance level before invocation.

#### Scenario: Skill is advisory
- **WHEN** a skill only summarizes, grades, or structures retrieved evidence
- **THEN** it may return advisory output without creating canonical candidates
- **AND** its governance level is `advisory`

#### Scenario: Skill produces identity or authority candidates
- **WHEN** a skill produces canonical, authority, institutional, geographic, or linked-data candidates
- **THEN** the output SHALL be marked as review-required unless a governed promotion policy explicitly permits otherwise
- **AND** its governance level is `review_required` or `governed_write_candidate`

#### Scenario: Skill requires human review
- **WHEN** a skill definition has `requires_human_review: true`
- **THEN** its output is always marked as review-required regardless of confidence score

### Requirement: Skill registry supports allowlist enforcement
UKIP SHALL enforce allowlist policies that control skill availability by tenant, organization, domain, and feature flag.

#### Scenario: Tenant-scoped allowlist
- **WHEN** a skill is allowed for tenant A but not tenant B
- **THEN** the RAG router for tenant A can invoke the skill
- **AND** the RAG router for tenant B cannot

#### Scenario: Domain-scoped allowlist
- **WHEN** a skill is allowed for the "science" domain but not "healthcare"
- **THEN** the skill is available only when the query is scoped to the "science" domain

### Requirement: Skill registry loading is configurable
UKIP SHALL support loading skill definitions from static configuration or a database-backed registry.

#### Scenario: Skills are loaded from static configuration
- **WHEN** UKIP starts with a static skill configuration file
- **THEN** the registry loads all valid skill definitions from the configuration

#### Scenario: Skills are loaded from database
- **WHEN** UKIP is configured to use a database-backed skill registry
- **THEN** the registry loads skill definitions from the database
- **AND** supports runtime addition and removal of skills without restart

### Requirement: Skill registry tests validate edge cases
UKIP SHALL include unit tests for invalid, disabled, and incompatible skill definitions.

#### Scenario: Test rejects skill without input schema
- **WHEN** a test registers a skill definition missing `input_schema`
- **THEN** the registry rejects it and it does not appear in available skills

#### Scenario: Test rejects skill without output schema
- **WHEN** a test registers a skill definition missing `output_schema`
- **THEN** the registry rejects it

#### Scenario: Test verifies disabled skill is not routable
- **WHEN** a test disables a skill via feature flag
- **THEN** the router does not consider it for any query

#### Scenario: Test verifies allowlist enforcement
- **WHEN** a test scopes a skill to a specific tenant
- **THEN** queries from other tenants do not receive that skill
