## ADDED Requirements

### Requirement: UKIP governs strategic decisions through enterprise architecture domains
UKIP SHALL classify strategic product and implementation decisions by affected enterprise architecture domains.

#### Scenario: Strategic spec is proposed
- **WHEN** a spec introduces or changes strategic platform behavior
- **THEN** it identifies affected business/stakeholder, data/semantic, application/service, UX/UI, infrastructure/operations, security/privacy, and GenAI domains as applicable

#### Scenario: Multi-domain decision is proposed
- **WHEN** a decision affects more than one architecture domain
- **THEN** UKIP identifies the primary domain, secondary domains, dependencies, risks, and success criteria

### Requirement: Enterprise architecture governs subordinate architecture specs
The enterprise architecture layer SHALL act as the high-level organizer for subordinate specs.

#### Scenario: Data governance spec is active
- **WHEN** `canonical-semantic-data-governance` defines semantic data rules
- **THEN** UKIP treats it as the data architecture backbone under enterprise architecture governance

#### Scenario: Stakeholder demo spec is active
- **WHEN** `research-stakeholder-executive-demo` defines stakeholder-facing workflows
- **THEN** UKIP maps it to business/stakeholder and UX/UI architecture domains
