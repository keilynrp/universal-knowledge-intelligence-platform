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

### Requirement: Skill registry separates advisory skills from governed candidate-producing skills
UKIP SHALL classify skills by governance level before invocation.

#### Scenario: Skill is advisory
- **WHEN** a skill only summarizes, grades, or structures retrieved evidence
- **THEN** it may return advisory output without creating canonical candidates

#### Scenario: Skill produces identity or authority candidates
- **WHEN** a skill produces canonical, authority, institutional, geographic, or linked-data candidates
- **THEN** the output SHALL be marked as review-required unless a governed promotion policy explicitly permits otherwise
