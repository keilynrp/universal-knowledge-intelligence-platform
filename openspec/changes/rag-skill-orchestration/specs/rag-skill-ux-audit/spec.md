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

#### Scenario: Direct RAG response has no skill badge
- **WHEN** a RAG response is answered directly without skill invocation
- **THEN** the UI does not show a skill badge or skill metadata
- **AND** the response is visually indistinguishable from pre-skill RAG behavior

#### Scenario: Skill confidence is visually indicated
- **WHEN** a skill-assisted response is displayed
- **THEN** the UI shows the confidence score with a visual indicator
- **AND** distinguishes high-confidence from low-confidence results

### Requirement: RAG API response includes skill invocation metadata
UKIP SHALL extend the RAG query endpoint response with optional skill invocation metadata.

#### Scenario: RAG response includes skill_invocations array
- **WHEN** a RAG response uses one or more skills
- **THEN** the response payload includes a `skill_invocations` array with skill_id, version, status, confidence, output, evidence references, and provenance

#### Scenario: Direct RAG response remains backward-compatible
- **WHEN** a RAG response is answered directly
- **THEN** the response payload either omits `skill_invocations` or includes an empty array
- **AND** existing RAG consumers continue to work without modification

#### Scenario: Skill outputs cite retrieved evidence
- **WHEN** a skill produces output
- **THEN** the output includes citations referencing specific retrieved evidence
- **AND** does not invent claims unsupported by the evidence set

### Requirement: RAG UI renders evidence, confidence, and provenance in expandable detail
UKIP SHALL render skill execution details in an expandable panel within the RAG response.

#### Scenario: Expandable panel shows evidence consumed
- **WHEN** the user expands the skill detail panel
- **THEN** the panel shows the evidence references that the skill consumed

#### Scenario: Expandable panel shows provenance
- **WHEN** the user expands the skill detail panel
- **THEN** the panel shows the skill version, execution timing, governance level, and policy result

#### Scenario: Expandable panel shows review CTA
- **WHEN** the skill output has `requires_review` status
- **THEN** the expandable panel includes an action path to the relevant review queue (e.g., authority review)

### Requirement: Skill invocation audit trail is preserved
UKIP SHALL persist an audit trail for every skill invocation and policy-blocked skill attempt.

#### Scenario: Audit event is created for invocation
- **WHEN** a skill is invoked
- **THEN** UKIP records user/session context, tenant/domain scope, skill ID/version, input evidence references, output status, confidence, timing, and policy result

#### Scenario: Audit event is created for policy block
- **WHEN** a skill invocation is blocked by policy
- **THEN** UKIP records the blocking policy, user context, query text, and the skill that was blocked

### Requirement: RAG UI governance and safety labels are visible
UKIP SHALL display governance-aware labels for skill status, policy decisions, and review requirements.

#### Scenario: Policy-blocked response shows governance explanation
- **WHEN** a skill is blocked by governance policy
- **THEN** the UI shows a governance label explaining why the operation was not permitted
- **AND** does not present the block as a system failure

#### Scenario: Review-required output shows governance label
- **WHEN** a skill output requires review
- **THEN** the UI shows a governance label indicating that the output needs human review before it can be acted upon

#### Scenario: Advisory skill output shows advisory label
- **WHEN** an advisory skill produces output
- **THEN** the UI shows an advisory label indicating that the output is informational and does not create canonical candidates

### Requirement: RAG UI translations cover skill-related copy
UKIP SHALL provide EN/ES translations for skill statuses, governance labels, and audit copy.

#### Scenario: English translations exist for skill UI
- **WHEN** the UI locale is English
- **THEN** all skill statuses (completed, completed_with_warnings, insufficient_evidence, requires_review, policy_blocked, failed), governance labels, evidence panel labels, and review CTA copy are defined

#### Scenario: Spanish translations exist for skill UI
- **WHEN** the UI locale is Spanish
- **THEN** equivalent Spanish labels are defined for all skill-related UI copy

### Requirement: RAG UI component tests cover skill-assisted responses
UKIP SHALL include component tests for direct RAG and skill-assisted RAG message rendering.

#### Scenario: Test verifies skill badge rendering
- **WHEN** a test provides a RAG response with a skill invocation
- **THEN** the component renders the skill badge with correct name, status, and confidence

#### Scenario: Test verifies direct RAG without skill badge
- **WHEN** a test provides a direct RAG response
- **THEN** the component renders without a skill badge

#### Scenario: Test verifies review CTA rendering
- **WHEN** a test provides a skill response with requires_review status
- **THEN** the component renders the review CTA with correct action path

#### Scenario: Test verifies policy-blocked rendering
- **WHEN** a test provides a policy-blocked response
- **THEN** the component renders the governance explanation without error styling
