## 1. Product and architecture framing

- [ ] 1.1 Define RAG skill orchestration as a governed agentic AI capability under enterprise architecture governance.
- [ ] 1.2 Document dependency on canonical semantic data governance and provenance layering.
- [ ] 1.3 Identify first-phase skills: `evidence-grading`, `citation-grounding`, and `stakeholder-briefing`.
- [ ] 1.4 Identify second-phase skills: `affiliation-reconciliation`, `geo-entity-resolution`, and `bibliographic-normalization`.

## 2. Skill registry contract

- [ ] 2.1 Define backend `SkillDefinition` schema with ID, version, description, input/output schema, governance level, and allowed evidence types.
- [ ] 2.2 Add registry loading from static configuration or database-backed registry.
- [ ] 2.3 Add allowlist enforcement by tenant/org, domain, and feature flag.
- [ ] 2.4 Add unit tests for invalid, disabled, and incompatible skill definitions.

## 3. RAG skill router

- [ ] 3.1 Define router input contract: user query, retrieved evidence summary, domain scope, user role, and available skills.
- [ ] 3.2 Implement routing decisions: direct answer, single skill, plan candidate, or policy block.
- [ ] 3.3 Require confidence and policy reasons in every routing decision.
- [ ] 3.4 Add tests for direct RAG, skill-assisted RAG, insufficient evidence, and policy-blocked scenarios.

## 4. Skill execution service

- [ ] 4.1 Define `SkillInvocation` record with evidence refs, status, confidence, output, provenance, and timing.
- [ ] 4.2 Validate skill input and output schemas.
- [ ] 4.3 Enforce timeout, failure handling, and safe fallback to direct RAG.
- [ ] 4.4 Persist audit events for every invocation.
- [ ] 4.5 Add tests for completed, failed, timed-out, and review-required invocations.

## 5. RAG API integration

- [ ] 5.1 Extend RAG query endpoint response with optional `skill_invocations`.
- [ ] 5.2 Ensure direct RAG answers remain backward-compatible.
- [ ] 5.3 Ensure skill outputs cite retrieved evidence and do not invent unsupported claims.
- [ ] 5.4 Add API tests for response shape and evidence traceability.

## 6. Frontend RAG UX

- [ ] 6.1 Render a compact skill badge when a response uses a skill.
- [ ] 6.2 Render evidence, confidence, status, and provenance details in an expandable panel.
- [ ] 6.3 Render review/action CTAs for `requires_review` outputs.
- [ ] 6.4 Add EN/ES translations for skill statuses, governance labels, and audit copy.
- [ ] 6.5 Add component tests for direct RAG and skill-assisted RAG messages.

## 7. Governance and safety

- [ ] 7.1 Prevent skills from directly mutating canonical identity.
- [ ] 7.2 Require review for authority, institutional, geographic, and linked-data candidate outputs unless a governed promotion policy exists.
- [ ] 7.3 Add policy-blocked copy for unsupported or unauthorized requests.
- [ ] 7.4 Ensure all skill outputs preserve tenant/org/domain scope.

## 8. Initial skill implementations

- [ ] 8.1 Implement read-only `evidence-grading` skill over retrieved evidence.
- [ ] 8.2 Implement read-only `citation-grounding` skill that maps claims to evidence references.
- [ ] 8.3 Implement `stakeholder-briefing` skill for audience-aware decision narrative.
- [ ] 8.4 Add regression tests for all initial skills.

## 9. Validation

- [ ] 9.1 Run backend unit tests for registry, router, execution, and RAG response contracts.
- [ ] 9.2 Run frontend tests for skill-assisted RAG rendering.
- [ ] 9.3 Run `npm exec tsc -- --noEmit --pretty false` in `frontend`.
- [ ] 9.4 Run `npx openspec validate rag-skill-orchestration --strict`.
- [ ] 9.5 Manual smoke test: ask RAG a direct question, a skill-eligible question, and an unsupported agentic request.
