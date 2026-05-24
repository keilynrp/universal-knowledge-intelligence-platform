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

#### Scenario: Skill input validation failure produces clear error
- **WHEN** skill input fails schema validation
- **THEN** UKIP records the validation error with specific field-level details
- **AND** does not invoke the skill

#### Scenario: Skill output validation failure triggers warning
- **WHEN** a skill produces output that fails schema validation
- **THEN** UKIP marks the invocation as `completed_with_warnings`
- **AND** includes the validation errors in the invocation audit record

### Requirement: Skills cannot silently mutate canonical data
RAG-invoked skills SHALL NOT directly overwrite canonical identity, authority resolution, enrichment observations, or linked-data mappings.

#### Scenario: Skill proposes a canonical candidate
- **WHEN** a skill proposes a canonical or authority candidate
- **THEN** UKIP stores it as a candidate with provenance and review status
- **AND** does not promote it to canonical identity without governed promotion rules

#### Scenario: Skill attempts direct canonical write
- **WHEN** a skill output attempts to directly modify canonical identity fields
- **THEN** UKIP blocks the write
- **AND** records the blocked attempt in the audit trail

### Requirement: Skill invocation records are well-structured
UKIP SHALL define a structured `SkillInvocation` record for every skill execution.

#### Scenario: Invocation record includes required fields
- **WHEN** a skill is invoked
- **THEN** the invocation record includes query_id, skill_id, skill_version, input evidence references, output, status, confidence, provenance, timing (start/end/duration), and review status

#### Scenario: Invocation record includes output status
- **WHEN** a skill completes
- **THEN** the status is one of: `completed`, `completed_with_warnings`, `insufficient_evidence`, `requires_review`, `policy_blocked`, or `failed`

### Requirement: Skill execution enforces timeout and failure handling
UKIP SHALL enforce timeout limits and provide safe fallback behavior when skills fail.

#### Scenario: Skill exceeds timeout
- **WHEN** a skill execution exceeds the declared `timeout_ms`
- **THEN** UKIP terminates the execution
- **AND** marks the invocation as `failed` with timeout as the failure reason
- **AND** falls back to direct RAG if evidence supports a grounded answer

#### Scenario: Skill throws runtime error
- **WHEN** a skill throws an unhandled error during execution
- **THEN** UKIP marks the invocation as `failed`
- **AND** records the error class and message without exposing internal details to the user
- **AND** falls back to direct RAG with a user-facing explanation

#### Scenario: Fallback to direct RAG is evidence-grounded
- **WHEN** a skill fails and UKIP falls back to direct RAG
- **THEN** the fallback response is based on retrieved evidence
- **AND** the response indicates that the skill could not complete and the answer is from direct RAG

### Requirement: Skill execution persists audit events
UKIP SHALL persist an audit event for every skill invocation, including successful, failed, and policy-blocked attempts.

#### Scenario: Successful invocation audit
- **WHEN** a skill completes successfully
- **THEN** UKIP persists an audit event with user/session context, tenant/domain scope, skill ID/version, input evidence refs, output summary, confidence, timing, and status

#### Scenario: Failed invocation audit
- **WHEN** a skill fails
- **THEN** UKIP persists an audit event with the failure reason, timing, and the evidence that was provided

#### Scenario: Policy-blocked attempt audit
- **WHEN** a skill invocation is blocked by policy
- **THEN** UKIP persists an audit event recording the blocking policy, user context, and the query that triggered the block

### Requirement: Skill execution tests cover all outcome paths
UKIP SHALL include tests for completed, failed, timed-out, and review-required invocations.

#### Scenario: Test verifies completed invocation
- **WHEN** a test invokes a skill with valid input and the skill succeeds
- **THEN** the invocation record has status `completed` with valid output and evidence references

#### Scenario: Test verifies failed invocation
- **WHEN** a test invokes a skill that throws an error
- **THEN** the invocation record has status `failed` with error details

#### Scenario: Test verifies timed-out invocation
- **WHEN** a test invokes a skill that exceeds its timeout
- **THEN** the invocation record has status `failed` with timeout reason

#### Scenario: Test verifies review-required invocation
- **WHEN** a test invokes a governed skill that produces authority candidates
- **THEN** the invocation record has status `requires_review`
