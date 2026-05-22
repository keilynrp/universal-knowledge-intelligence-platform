## ADDED Requirements

### Requirement: RAG UI exposes skill use transparently
UKIP SHALL make skill-assisted RAG responses visibly distinguishable from direct RAG responses.

#### Scenario: Response uses a skill
- **WHEN** a RAG response includes a skill invocation
- **THEN** the UI shows the skill name, status, confidence, and evidence summary
- **AND** provides access to provenance and citations

#### Scenario: Skill output requires review
- **WHEN** a skill output has `requires_review` status
- **THEN** the UI shows review-required copy and a relevant action path when available

#### Scenario: Skill invocation is blocked
- **WHEN** policy blocks a skill invocation
- **THEN** the UI explains that the request could not be completed under current governance rules
- **AND** avoids presenting blocked output as a failed system error

### Requirement: Skill invocation audit trail is preserved
UKIP SHALL persist an audit trail for every skill invocation and policy-blocked skill attempt.

#### Scenario: Audit event is created
- **WHEN** a skill is invoked or blocked
- **THEN** UKIP records user/session context, tenant/domain scope, skill ID/version, input evidence references, output status, confidence, timing, and policy result
