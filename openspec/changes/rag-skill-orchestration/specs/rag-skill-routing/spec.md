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

#### Scenario: Multi-skill plan is identified
- **WHEN** a user question could benefit from multiple skills in sequence
- **THEN** the router identifies a multi-skill plan candidate
- **AND** does not execute the plan automatically unless governed chaining policy permits it
- **AND** presents the plan to the user for review when chaining is not auto-approved

### Requirement: Skill routing decisions are auditable
UKIP SHALL record routing decisions that lead to skill invocation, policy block, or escalation.

#### Scenario: Router selects a skill
- **WHEN** the router selects a skill
- **THEN** UKIP records the selected skill, routing reason, confidence, policy result, and evidence scope

#### Scenario: Router blocks a skill
- **WHEN** the router blocks a skill invocation
- **THEN** UKIP records the blocked skill, blocking policy, user context, and the evidence that triggered the block

#### Scenario: Router falls back to direct RAG
- **WHEN** the router determines no skill is needed or available
- **THEN** UKIP records the fallback decision and the reason no skill was selected

### Requirement: Router input contract is well-defined
UKIP SHALL define a structured input contract for the skill router.

#### Scenario: Router input includes required fields
- **WHEN** the router receives a query
- **THEN** the input includes user query text, retrieved evidence summary, domain scope, user role, tenant context, and available skill list

#### Scenario: Router considers user role for skill eligibility
- **WHEN** a skill requires editor or admin role
- **THEN** the router does not route viewer-role queries to that skill

#### Scenario: Router considers domain scope
- **WHEN** a query is scoped to a specific domain
- **THEN** the router only considers skills allowed for that domain

### Requirement: Routing confidence and policy reasons are required
UKIP SHALL require confidence scores and policy reasons in every routing decision.

#### Scenario: Routing decision includes confidence
- **WHEN** the router makes a decision
- **THEN** the decision includes a confidence score indicating how well the query matches the selected route

#### Scenario: Routing decision includes policy reason
- **WHEN** the router makes a decision
- **THEN** the decision includes a policy reason explaining why the route was chosen, blocked, or escalated

### Requirement: Skill routing tests cover all decision paths
UKIP SHALL include tests for direct RAG, skill-assisted RAG, insufficient evidence, and policy-blocked scenarios.

#### Scenario: Test verifies direct RAG routing
- **WHEN** a test provides a simple factual question with sufficient evidence
- **THEN** the router selects direct RAG answer without skill invocation

#### Scenario: Test verifies skill-assisted routing
- **WHEN** a test provides a question that matches a registered skill input contract
- **THEN** the router selects the appropriate skill

#### Scenario: Test verifies insufficient evidence routing
- **WHEN** a test provides a skill-eligible question with no retrieved evidence
- **THEN** the router returns insufficient-evidence status

#### Scenario: Test verifies policy-blocked routing
- **WHEN** a test provides a query that matches a disabled or unauthorized skill
- **THEN** the router returns policy-blocked status with explanation
