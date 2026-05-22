## ADDED Requirements

### Requirement: RAG routes queries through a governed skill router
UKIP SHALL evaluate whether a RAG query should be answered directly, assisted by a skill, escalated for review, or blocked by policy.

#### Scenario: Direct RAG answer is sufficient
- **WHEN** retrieved evidence can answer the user question without specialized processing
- **THEN** UKIP SHALL answer with grounded RAG behavior
- **AND** SHALL NOT invoke a skill unnecessarily

#### Scenario: Skill-assisted answer is appropriate
- **WHEN** the user question requires a registered skill and retrieved evidence satisfies the skill input contract
- **THEN** UKIP SHALL invoke the approved skill
- **AND** SHALL pass only scoped evidence that the current user and tenant are authorized to access

#### Scenario: Evidence is insufficient
- **WHEN** a skill-eligible question lacks sufficient retrieved evidence
- **THEN** UKIP SHALL return an insufficient-evidence status or ask for more data
- **AND** SHALL NOT fabricate skill output

#### Scenario: Policy blocks skill invocation
- **WHEN** the requested operation is unauthorized, unsafe, or outside the skill governance policy
- **THEN** UKIP SHALL block the skill invocation
- **AND** SHALL return a policy-aware explanation suitable for the user role

### Requirement: Skill routing decisions are auditable
UKIP SHALL record routing decisions that lead to skill invocation, policy block, or escalation.

#### Scenario: Router selects a skill
- **WHEN** the router selects a skill
- **THEN** UKIP records the selected skill, routing reason, confidence, policy result, and evidence scope
