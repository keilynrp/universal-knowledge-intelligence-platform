## Why

UKIP already has the ingredients for a scientific intelligence product: demo seeding, executive dashboard, institutional benchmarks, impact projection, quality signals, and report export. The strategic gap is that research stakeholders still need to assemble the story themselves.

For rectorates, research offices, innovation teams, and external evaluators, the product needs to demonstrate a defensible decision journey in minutes:

```
Load demo corpus -> read executive signal -> inspect evidence -> choose next action -> export stakeholder brief
```

Without this guided path, UKIP looks like a powerful analytics workbench. With it, UKIP becomes a research intelligence product that helps institutions decide what to fund, review, improve, or communicate.

## What Changes

- **New**: Research stakeholder demo mode that detects when the demo corpus is available and presents a guided executive journey.
- **New**: Decision readout contract that standardizes "what we know", "what is emerging", "confidence", "gaps", and "recommended action" across dashboard and reports.
- **New**: Evidence traceability affordances from each executive recommendation to the supporting records, concepts, benchmark rules, quality metrics, and sources.
- **New**: Stakeholder audience presets for leadership, research office, investigator, innovation/transfer, and evaluator.
- **Modified**: Executive dashboard becomes the primary landing surface after demo seed/import success.
- **Modified**: Executive brief export must include the same decision readout and evidence traceability visible in the dashboard.

## Capabilities

### New Capabilities

- `research-stakeholder-demo-flow`: Guided end-to-end flow for research stakeholders from demo seed/import to dashboard and brief.
- `executive-decision-readout`: Shared decision narrative model used by dashboard and reports.
- `evidence-traceability-ui`: UI affordances that connect recommendations to underlying evidence.
- `stakeholder-audience-presets`: Audience-specific framing for the same research corpus.

### Modified Capabilities

- `real-demo-seed`: Demo seed should produce a corpus suitable for executive stakeholder walkthroughs.
- `dashboard-summary`: Dashboard summary should expose enough structured fields for decision readout and traceability.
- `report-builder`: Brief exports should preserve the dashboard's decision readout rather than requiring manual interpretation.

## Impact

- **Backend**: Extend dashboard summary or add a narrow decision-readout endpoint. Reuse existing analytics, benchmark, quality, and demo data contracts.
- **Frontend**: Add guided demo callouts, stakeholder preset selector, traceability panels, and brief handoff CTA.
- **Reports**: Include decision readout, recommended action, confidence, gaps, and evidence appendix in PDF/HTML export.
- **Tests**: Add regression coverage for demo flow, decision-readout fallback behavior, and traceability links.

## Success Criteria

- A new stakeholder can seed or open the demo and understand UKIP's research intelligence value in under 5 minutes.
- The executive dashboard answers: what do we know, what is emerging, how confident are we, what is missing, and what should we do next.
- Every recommendation has visible supporting evidence.
- The exported brief matches the dashboard narrative and can be shared with non-technical stakeholders.
