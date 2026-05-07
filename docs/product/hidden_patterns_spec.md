# Hidden Patterns Spec

## Purpose

UKIP must identify non-obvious signals inside an imported portfolio without forcing users to interpret raw mining outputs.

The feature exposes a compact, explainable `hidden_patterns` payload that can be reused by:

- Executive Dashboard
- catalog/import-batch exploration
- final stakeholder brief
- future portal-specific analytics

## Scope

The first implementation is deterministic, dependency-light, and explainable. It does not introduce a black-box ML service.

Inputs:

- `domain_id`
- optional `import_batch_id`
- optional `provider`
- optional `portal_slug`
- tenant scope from authenticated user

Outputs:

```json
{
  "scope": {
    "domain_id": "science",
    "import_batch_id": 123,
    "provider": "wos",
    "portal_slug": "science-portal"
  },
  "summary": {
    "records_analyzed": 1200,
    "patterns_found": 4,
    "highest_impact_score": 88
  },
  "patterns": [
    {
      "id": "impact_outlier:42",
      "type": "impact_outlier",
      "label": "High-impact outlier detected",
      "confidence": "high",
      "impact_score": 88,
      "evidence": "This record is far above the portfolio citation baseline.",
      "entities": [{"id": 42, "label": "Example paper"}],
      "recommended_action": "Use this record as an anchor in the stakeholder brief."
    }
  ]
}
```

## Pattern Types

- `semantic_cluster`: repeated concepts that behave as a strong thematic concentration.
- `impact_outlier`: entities whose citation signal is much higher than the portfolio baseline.
- `quality_gap`: low-quality records that can distort executive interpretation.
- `provider_gap`: source/provider imbalance or low provider coverage.
- `collaboration_bridge`: graph-connected entities that connect or concentrate relationships.
- `duplicate_candidate`: records with highly similar normalized labels.

## UX Rules

- Show at most 4-6 patterns in dashboard surfaces.
- Every pattern must include evidence and a recommended action.
- Avoid algorithm jargon in primary UI labels.
- Technical method names may appear in secondary copy or tooltips.
- Brief copy must explain what the pattern means for decision-making.

## Acceptance Criteria

- Dashboard summary includes `hidden_patterns`.
- Dedicated endpoint supports `domain_id`, `import_batch_id`, `provider`, and `portal_slug`.
- Final brief can include a `Hidden Patterns` section.
- Output is deterministic for the same dataset.
- Empty datasets return a valid empty response.
- Tenant scoping is preserved.
