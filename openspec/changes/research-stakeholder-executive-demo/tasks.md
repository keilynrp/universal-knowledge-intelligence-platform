## 1. Decision-readout contract

- [ ] 1.1 Define a `DecisionReadout` TypeScript interface shared by dashboard/report frontend code.
- [ ] 1.2 Add a builder that derives `known`, `emerging`, `confidence`, `missing`, and `recommended_action` from existing `/dashboard/summary` data.
- [ ] 1.3 Add safe fallbacks for empty corpus, partial enrichment, missing benchmark, and missing concept signals.
- [ ] 1.4 Add unit/regression tests for the builder with complete, partial, and empty dashboard payloads.

## 2. Research stakeholder demo flow

- [ ] 2.1 Add `mode=stakeholder-demo` support to `/analytics/dashboard`.
- [ ] 2.2 Add a compact guided walkthrough rail with corpus readiness, executive signal, evidence, and export steps.
- [ ] 2.3 Update demo seed/import success CTAs to point to stakeholder demo mode.
- [ ] 2.4 Add "Reset walkthrough" and "Dismiss walkthrough" behavior persisted per browser.

## 3. Audience presets

- [ ] 3.1 Define audience presets: leadership, research office, investigator, innovation/transfer, evaluator.
- [ ] 3.2 Add an audience selector on stakeholder demo mode.
- [ ] 3.3 Adjust readout labels, CTAs, and report framing by audience without changing analytics calculations.
- [ ] 3.4 Add EN/ES translations for preset names, descriptions, and CTAs.

## 4. Evidence traceability

- [ ] 4.1 Extend recommendation UI to show compact evidence references.
- [ ] 4.2 Add expandable evidence panels linking to supporting records, benchmark rules, concepts, quality filters, and sources when available.
- [ ] 4.3 Add graceful fallback copy when evidence is unavailable.
- [ ] 4.4 Track evidence panel interactions via existing frontend analytics helper.

## 5. Executive brief handoff

- [ ] 5.1 Pass `audience`, `benchmark_profile`, `domain`, and `mode=stakeholder-demo` from dashboard to report builder.
- [ ] 5.2 Add decision-readout section to report builder preview.
- [ ] 5.3 Add evidence appendix section to PDF/HTML export.
- [ ] 5.4 Ensure exported brief preserves the same recommendation, confidence, gaps, and evidence shown in dashboard.

## 6. Validation

- [ ] 6.1 Add frontend tests for default stakeholder demo rendering and audience preset switching.
- [ ] 6.2 Add backend/API regression if a new decision-readout endpoint is introduced.
- [ ] 6.3 Validate `npx tsc --noEmit`.
- [ ] 6.4 Validate `npx openspec validate research-stakeholder-executive-demo --strict`.
- [ ] 6.5 Manual smoke test: seed demo -> dashboard stakeholder mode -> evidence expand -> brief builder -> export.
