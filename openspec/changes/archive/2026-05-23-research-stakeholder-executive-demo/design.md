## Context

The current product has strong analytical primitives but lacks a single guided storyline for research stakeholders. The executive dashboard already shows many of the right signals, and the report builder can package output, but the handoff between "analysis" and "decision" needs to be explicit, repeatable, and audience-aware.

The target user is not only a data operator. It includes:

- Rectorate / executive leadership: needs strategic decisions and confidence.
- Research office: needs readiness, gaps, and repeatable review workflows.
- Investigator / PI: needs evidence, impact, and next improvement steps.
- Innovation / transfer office: needs translational potential and external attention.
- Evaluator: needs defensibility, provenance, and limitations.

## Goals / Non-Goals

**Goals:**
- Make the demo path feel like a product walkthrough, not a collection of pages.
- Create a shared decision-readout model used by dashboard and report export.
- Preserve evidence traceability for each recommendation.
- Make audience framing explicit without changing the underlying corpus.
- Keep implementation additive and compatible with existing demo/dashboard/report surfaces.

**Non-Goals:**
- Replacing the analytics dashboard with a separate marketing page.
- Building a generic onboarding engine for all product areas.
- Adding new external data providers.
- Implementing full workflow automation or CRM-style stakeholder management.

## Decisions

### D1: Guided flow lives in product surfaces, not a landing page

**Decision:** The first experience after demo seed/import should route into the executive dashboard with guided panels and next-step CTAs.

**Rationale:** Stakeholders need to see the real analytical product immediately. A marketing-style explanation would dilute the value moment.

### D2: Decision readout is a shared contract

**Decision:** Dashboard and reports should use the same conceptual model:

- `known`: corpus state and measurable coverage
- `emerging`: concepts, patterns, external attention, or topic acceleration
- `confidence`: benchmark readiness, quality, enrichment coverage
- `missing`: top gaps and limitations
- `recommended_action`: next step with evidence

**Rationale:** If the dashboard and PDF tell different stories, stakeholders lose trust. A shared contract keeps narrative consistent.

### D3: Evidence traceability is mandatory for recommendations

**Decision:** Every recommendation must expose evidence references, even if the UI initially renders them as compact links or expandable panels.

**Rationale:** Research stakeholders are sensitive to unsupported claims. Traceability turns the brief from "AI generated summary" into "defensible intelligence artifact".

### D4: Audience presets change framing, not facts

**Decision:** Audience presets adjust labels, emphasis, CTAs, and report framing. They do not alter underlying calculations.

**Rationale:** This keeps the product honest while making it useful for multiple stakeholder conversations.

## Proposed UX Flow

1. User opens demo/import success state.
2. Primary CTA opens `/analytics/dashboard?mode=stakeholder-demo&audience=leadership`.
3. Dashboard shows a compact "Stakeholder Walkthrough" rail:
   - Step 1: Corpus readiness
   - Step 2: Executive signal
   - Step 3: Evidence behind recommendation
   - Step 4: Export stakeholder brief
4. User changes audience preset if needed.
5. Each recommendation can expand evidence references.
6. "Prepare Executive Brief" carries domain, benchmark profile, audience, and selected evidence into reports.
7. Report export includes the same decision readout and evidence appendix.

## Data Shape

Initial implementation may derive this client-side from `/dashboard/summary`, but the target contract is:

```json
{
  "domain_id": "science",
  "audience": "leadership",
  "known": {
    "title": "The corpus is measurable",
    "body": "24 records, 100% enriched, 20 concepts available.",
    "metrics": [{"label": "Enrichment", "value": "100%"}]
  },
  "emerging": {
    "title": "AI-assisted research assessment",
    "evidence": "Appears across 6 records with recent acceleration."
  },
  "confidence": {
    "status": "watch",
    "readiness_pct": 72,
    "drivers": ["coverage", "quality", "benchmark rules"]
  },
  "missing": {
    "top_gap": "Quality threshold",
    "evidence": "Observed 64, expected 70."
  },
  "recommended_action": {
    "title": "Review low-quality records before external presentation",
    "priority": "high",
    "evidence_refs": [
      {"type": "benchmark_rule", "id": "quality_min"},
      {"type": "entity_filter", "query": "quality<0.7"}
    ]
  }
}
```

## Risks / Trade-offs

- **Risk: Dashboard becomes too dense.** Mitigation: Use a guided rail and expandable evidence panels rather than adding large new sections.
- **Risk: Recommendations look deterministic.** Mitigation: Always show confidence, gaps, and limitations alongside actions.
- **Risk: Audience presets drift into separate logic.** Mitigation: Keep presets as presentation metadata only.
- **Risk: Export diverges from dashboard.** Mitigation: Use the same decision-readout builder for both surfaces.

## Rollout Plan

1. Add spec-backed decision-readout types and fallback builder.
2. Add guided stakeholder mode to dashboard.
3. Add evidence panels for current recommendations.
4. Carry audience and evidence selection into report builder.
5. Add report sections for decision readout and evidence appendix.
6. Validate with seeded demo corpus and production-like empty/partial data states.
