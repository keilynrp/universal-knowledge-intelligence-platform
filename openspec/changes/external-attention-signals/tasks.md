## 1. Priority 1 - Attention Score MVP

- [x] 1.1 Define `ExternalAttentionObservation` and `ExternalAttentionSnapshot` storage strategy or JSON MVP fallback.
- [x] 1.2 Create `backend/analyzers/external_attention.py` with deterministic score calculation.
- [x] 1.3 Implement source weights, recency multiplier, score normalization, and category mapping.
- [x] 1.4 Add endpoint for entity-level attention summary.
- [x] 1.5 Add tests for empty data, single-source data, multi-source weighting, recency decay, and score cap.
- [x] 1.6 Add an attention badge to entity detail.
- [x] 1.7 Add a compact attention card to executive dashboard summary.

## 2. Priority 2 - Source Breakdown

- [x] 2.1 Implement source taxonomy validation.
- [x] 2.2 Return counts, weighted contribution, and share per source type.
- [x] 2.3 Add source breakdown UI component with compact labels and tooltips.
- [x] 2.4 Add tests for unknown source types, zero counts, and percentage totals.

## 3. Priority 3 - Attention Timeline

- [x] 3.1 Aggregate observations by month by default.
- [x] 3.2 Support optional day granularity for short windows.
- [x] 3.3 Add spike metadata to timeline buckets.
- [x] 3.4 Render a compact timeline in entity detail.
- [x] 3.5 Add tests for empty ranges and period aggregation.

## 4. Priority 4 - Spike Explanations

- [x] 4.1 Generate deterministic explanations from top source contribution and period deltas.
- [x] 4.2 Include evidence snippets only when source title/url/snippet is available.
- [x] 4.3 Add explanation cards to entity detail.
- [x] 4.4 Add tests for explanation priority and sparse evidence fallback.

## 5. Priority 5 - Emerging Attention Alerts

- [x] 5.1 Implement `new_attention`, `attention_spike`, `policy_mention`, and `cross_source_momentum` alert rules.
- [x] 5.2 Add alert severity and confidence fields.
- [x] 5.3 Add top 3 attention alerts to executive dashboard.
- [x] 5.4 Add tests for baseline thresholds, false-positive guards, and alert ordering.

## 6. Integration and Governance

- [x] 6.1 Document that attention is not quality or citation impact.
- [x] 6.2 Add tenant scoping and domain filters to all endpoints.
- [x] 6.3 Add feature flag for external attention signals.
- [x] 6.4 Add import path for customer-provided external attention observations.
- [ ] 6.5 Revisit Rust engine delegation only after Python scoring is validated.
