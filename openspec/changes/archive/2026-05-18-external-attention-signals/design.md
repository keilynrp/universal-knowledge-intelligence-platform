# External Attention Signals Design

## Design Principles

- External attention is a contextual signal, not a quality metric.
- Every score must be explainable from source counts, recency, and weights.
- The MVP must work with partial data and degrade gracefully.
- UX should stay compact: badge, breakdown, timeline, and explanation.
- Implementation should reuse UKIP's existing entity, concept, dashboard, and analyzer patterns.

## Prioritization

### P0: Data Contract and Deterministic Scoring

Create a stable response shape and scoring function before adding many sources.

Initial score inputs:

- `source_type`
- `mention_count`
- `first_seen_at`
- `last_seen_at`
- `entity_id` or normalized external identifier
- optional `url`, `title`, `publisher`, `snippet`

Initial source weights:

| Source type | Weight | Rationale |
| --- | ---: | --- |
| policy | 8 | Strong decision-making signal |
| news | 5 | Broad external relevance |
| wikipedia | 4 | Public reference signal |
| repository | 3 | Technical reuse or reproducibility signal |
| blog | 2 | Specialist commentary |
| scholarly_web | 2 | Academic web mention outside citation count |
| social_web | 1 | Noisy awareness signal |

Score formula MVP:

```text
raw_score = sum(log1p(mention_count) * source_weight * recency_multiplier)
attention_score = min(100, round(raw_score * normalization_factor))
```

`recency_multiplier` should favor recent mentions without erasing older sustained attention.

### P1: Source Breakdown

Expose source composition as percentages and counts. This prevents a single score from becoming opaque.

### P2: Timeline

Aggregate by month for historical portfolios and by day only when data volume supports it. This keeps queries cheap and avoids chart noise.

### P3: Explanations

Generate deterministic explanations from the top contributors:

- top source type
- most recent high-weight mention
- largest period-over-period increase
- related concept/entity if available

### P4: Alerts

Use rule-based alerts:

- `new_attention`: first external attention observed
- `attention_spike`: current period exceeds rolling baseline
- `policy_mention`: policy source observed
- `cross_source_momentum`: at least 3 source types active in current period

## Suggested API Shape

```json
{
  "scope": {
    "domain_id": "science",
    "entity_id": 123,
    "cluster_id": null
  },
  "summary": {
    "attention_score": 67,
    "category": "high",
    "percentile": 82,
    "total_mentions": 43,
    "active_sources": 4,
    "last_seen_at": "2026-05-15T00:00:00Z"
  },
  "source_breakdown": [
    {
      "source_type": "policy",
      "mentions": 3,
      "weighted_contribution": 24,
      "share": 0.35
    }
  ],
  "timeline": [
    {
      "period": "2026-05",
      "mentions": 12,
      "score_delta": 8,
      "top_source_type": "news"
    }
  ],
  "explanations": [
    {
      "type": "policy_mention",
      "label": "Policy attention detected",
      "evidence": "Three policy mentions contributed 35% of the current attention score."
    }
  ],
  "alerts": [
    {
      "type": "attention_spike",
      "severity": "medium",
      "label": "External attention is above baseline"
    }
  ]
}
```

## Data Strategy

MVP can start with imported observations from CSV/API payloads and a small table:

- `ExternalAttentionObservation`
- `ExternalAttentionSnapshot`

Avoid building source-specific crawlers in the first release. Add connector jobs later only for sources with stable APIs or customer-provided exports.

## UX Placement

- Executive Dashboard: one compact card plus top 3 alerts.
- Entity Detail: badge, source breakdown, and timeline.
- Topics/Trends: optional attention column for concepts.
- Reports: short paragraph explaining external attention in decision language.

## Risks

- Score can be misread as quality. Mitigation: labels and help text must say "attention", not "impact quality".
- Social/web mentions can be noisy. Mitigation: low default weight and source breakdown visible.
- Sparse data can create false spikes. Mitigation: require minimum baseline or mark alert confidence as low.
- Connector sprawl. Mitigation: support imported observations first.
