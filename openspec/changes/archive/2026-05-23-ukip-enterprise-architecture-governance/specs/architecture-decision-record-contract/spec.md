## ADDED Requirements

### Requirement: Strategic decisions have architecture decision records
UKIP SHALL document strategic architecture decisions with a lightweight architecture decision record.

#### Scenario: Decision changes service boundaries
- **WHEN** UKIP changes a core service boundary, integration pattern, or API responsibility
- **THEN** an architecture decision record captures context, options, decision, rationale, risks, validation evidence, and related specs

#### Scenario: Decision changes semantic data governance
- **WHEN** UKIP changes canonical identity, provenance, authority resolution, or enrichment rules
- **THEN** an architecture decision record captures data impact and affected subordinate specs

### Requirement: Architecture decision records capture cross-domain impact
Architecture decision records SHALL capture business, data, service, UX/UI, infrastructure, security, and GenAI impact when applicable.

#### Scenario: AI-assisted reporting is introduced
- **WHEN** UKIP introduces GenAI-generated report narratives
- **THEN** the architecture decision record captures stakeholder value, evidence grounding, UX disclosure, service dependency, security/privacy considerations, and review requirements
