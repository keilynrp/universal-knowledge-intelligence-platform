## Context

RAG is currently a retrieval and answer-generation surface. Skills introduce a second layer: specialized operations that can act on evidence sets. The design goal is not to make the model "do anything"; it is to make UKIP's RAG module choose from bounded, observable, policy-controlled capabilities.

## Goals / Non-Goals

**Goals:**
- Define a governed skill lifecycle for RAG.
- Route user questions to direct RAG, skill-assisted RAG, or escalation.
- Require schema-validated inputs and outputs for every skill.
- Preserve evidence traceability and tenant/domain scope.
- Prepare the platform for future agentic AI workflows.

**Non-Goals:**
- Building a general-purpose plugin marketplace.
- Letting users execute arbitrary code from RAG.
- Allowing skills to overwrite canonical data directly.
- Implementing multi-step autonomous agents in the first release.

## Core Concepts

### Skill Registry

Each skill should declare:

- `skill_id`
- `display_name`
- `description`
- `version`
- `input_schema`
- `output_schema`
- `allowed_evidence_types`
- `allowed_domains`
- `governance_level`: `advisory | review_required | governed_write_candidate`
- `requires_human_review`
- `can_chain`
- `timeout_ms`
- `audit_category`

### Skill Router

The router decides:

- direct RAG answer,
- single skill invocation,
- multi-skill plan candidate,
- refusal/escalation when evidence or permissions are insufficient.

Routing should consider:

- user intent,
- retrieved evidence types,
- tenant/domain scope,
- skill availability,
- confidence threshold,
- governance policy,
- whether the query asks for a canonical data mutation.

### Skill Execution

Execution should:

1. Receive a scoped evidence set from RAG.
2. Validate evidence against the skill input schema.
3. Run the skill.
4. Validate skill output schema.
5. Attach citations, provenance, confidence, and review status.
6. Return output to the answer composer.
7. Persist an audit event.

### Skill Output Status

Skill outputs should use a controlled status:

- `completed`
- `completed_with_warnings`
- `insufficient_evidence`
- `requires_review`
- `policy_blocked`
- `failed`

## Governance Rules

- Skills SHALL NOT directly promote source or enrichment data into canonical identity.
- Skills MAY produce canonical candidates if governance rules allow.
- Skills that affect authority resolution, institutional identity, geographic identity, or linked-data alignment SHALL mark output as review-required unless confidence and policy thresholds are met.
- Skills SHALL preserve source IDs, entity IDs, and evidence references.
- Agentic chaining SHALL be disabled until every step can produce auditable evidence and policy decisions.

## Initial UX

The RAG response should show:

- answer narrative,
- skill used,
- evidence consumed,
- confidence,
- status,
- citations,
- review/action CTA when needed.

Example:

```text
Skill used: affiliation-reconciliation
Status: requires review
Confidence: 0.82
Evidence: 12 affiliations, 4 ROR candidates, 3 OpenAlex institution IDs
Action: Review candidate institution links
```

## Data Shape

```json
{
  "query_id": "ragq_123",
  "skill_invocations": [
    {
      "skill_id": "affiliation-reconciliation",
      "skill_version": "0.1.0",
      "status": "requires_review",
      "confidence": 0.82,
      "input_evidence_refs": [
        {"type": "entity", "id": 101},
        {"type": "authority_record", "id": 55}
      ],
      "output": {
        "candidate_organization": "Universidad de Puerto Rico",
        "authority_candidates": [
          {"source": "ROR", "id": "https://ror.org/...", "score": 0.82}
        ]
      },
      "provenance": {
        "generated_by": "skill",
        "model_or_engine": "ukip-skill-runner",
        "policy": "review_required"
      }
    }
  ]
}
```

## Rollout Plan

1. Define registry and invocation schemas.
2. Add one read-only advisory skill.
3. Integrate RAG response metadata and UI badge.
4. Add audit logging.
5. Add review-required flow for authority/canonical candidates.
6. Enable controlled multi-skill plan candidates after observability is proven.

## Risks / Trade-offs

- **Risk: Users over-trust skill outputs.** Mitigation: explicit status, confidence, citations, and review labels.
- **Risk: Skills duplicate enrichment services.** Mitigation: skills operate over retrieved evidence and call existing services where possible.
- **Risk: Agentic workflows become opaque.** Mitigation: persist every routing, policy, evidence, and output decision.
- **Risk: Skill routing adds latency.** Mitigation: start with single-skill routing, timeout budgets, and cached evidence summaries.
