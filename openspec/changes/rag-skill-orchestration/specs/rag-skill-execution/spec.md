## ADDED Requirements

### Requirement: Skill execution is schema-validated and evidence-grounded
UKIP SHALL validate skill inputs and outputs against declared schemas and require evidence references for skill-derived claims.

#### Scenario: Skill input is valid
- **WHEN** RAG invokes a skill
- **THEN** UKIP validates the evidence set and parameters against the skill input schema
- **AND** rejects execution if validation fails

#### Scenario: Skill output is returned
- **WHEN** a skill completes
- **THEN** UKIP validates the output schema
- **AND** attaches status, confidence, provenance, evidence references, and review status

#### Scenario: Skill cannot complete safely
- **WHEN** a skill times out, fails validation, or produces unsupported output
- **THEN** UKIP SHALL mark the invocation as failed or completed-with-warnings
- **AND** SHALL fall back to direct RAG only when the response can remain evidence-grounded

### Requirement: Skills cannot silently mutate canonical data
RAG-invoked skills SHALL NOT directly overwrite canonical identity, authority resolution, enrichment observations, or linked-data mappings.

#### Scenario: Skill proposes a canonical candidate
- **WHEN** a skill proposes a canonical or authority candidate
- **THEN** UKIP stores it as a candidate with provenance and review status
- **AND** does not promote it to canonical identity without governed promotion rules
