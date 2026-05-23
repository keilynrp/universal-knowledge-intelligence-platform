## 1. Product and architecture framing

- [x] 1.1 Define RAG skill orchestration as a governed agentic AI capability under enterprise architecture governance.
- [x] 1.2 Document dependency on canonical semantic data governance and provenance layering.
- [x] 1.3 Identify first-phase skills: `evidence-grading`, `citation-grounding`, and `stakeholder-briefing`.
- [x] 1.4 Identify second-phase skills: `affiliation-reconciliation`, `geo-entity-resolution`, and `bibliographic-normalization`.

## 2. Skill registry contract

- [x] 2.1 Define backend `SkillDefinition` schema with ID, version, description, input/output schema, governance level, and allowed evidence types.
- [x] 2.2 Add registry loading from static configuration or database-backed registry.
- [x] 2.3 Add allowlist enforcement by tenant/org, domain, and feature flag.
- [x] 2.4 Add unit tests for invalid, disabled, and incompatible skill definitions.

## 3. RAG skill router

- [x] 3.1 Define router input contract: user query, retrieved evidence summary, domain scope, user role, and available skills.
- [x] 3.2 Implement routing decisions: direct answer, single skill, plan candidate, or policy block.
- [x] 3.3 Require confidence and policy reasons in every routing decision.
- [x] 3.4 Add tests for direct RAG, skill-assisted RAG, insufficient evidence, and policy-blocked scenarios.

## 4. Skill execution service

- [x] 4.1 Define `SkillInvocation` record with evidence refs, status, confidence, output, provenance, and timing.
- [x] 4.2 Validate skill input and output schemas.
- [x] 4.3 Enforce timeout, failure handling, and safe fallback to direct RAG.
- [x] 4.4 Persist audit events for every invocation.
- [x] 4.5 Add tests for completed, failed, timed-out, and review-required invocations.

## 5. RAG API integration

- [x] 5.1 Extend RAG query endpoint response with optional `skill_invocations`.
- [x] 5.2 Ensure direct RAG answers remain backward-compatible.
- [x] 5.3 Ensure skill outputs cite retrieved evidence and do not invent unsupported claims.
- [x] 5.4 Add API tests for response shape and evidence traceability.

## 6. Frontend RAG UX

- [x] 6.1 Render a compact skill badge when a response uses a skill.
- [x] 6.2 Render evidence, confidence, status, and provenance details in an expandable panel.
- [x] 6.3 Render review/action CTAs for `requires_review` outputs.
- [x] 6.4 Add EN/ES translations for skill statuses, governance labels, and audit copy.
- [x] 6.5 Add component tests for direct RAG and skill-assisted RAG messages.

## 7. Governance and safety

- [x] 7.1 Prevent skills from directly mutating canonical identity.
- [x] 7.2 Require review for authority, institutional, geographic, and linked-data candidate outputs unless a governed promotion policy exists.
- [x] 7.3 Add policy-blocked copy for unsupported or unauthorized requests.
- [x] 7.4 Ensure all skill outputs preserve tenant/org/domain scope.

## 8. Initial skill implementations

- [x] 8.1 Implement read-only `evidence-grading` skill over retrieved evidence.
- [x] 8.2 Implement read-only `citation-grounding` skill that maps claims to evidence references.
- [x] 8.3 Implement `stakeholder-briefing` skill for audience-aware decision narrative.
- [x] 8.4 Add regression tests for all initial skills.

## 9. Validation

- [x] 9.1 Run backend unit tests for registry, router, execution, and RAG response contracts.
- [x] 9.2 Run frontend tests for skill-assisted RAG rendering.
- [x] 9.3 Run `npm exec tsc -- --noEmit --pretty false` in `frontend`.
- [x] 9.4 Run `npx openspec validate rag-skill-orchestration --strict`.
- [x] 9.5 Manual smoke test: ask RAG a direct question, a skill-eligible question, and an unsupported agentic request.
