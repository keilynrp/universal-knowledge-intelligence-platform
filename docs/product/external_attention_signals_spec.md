# External Attention Signals Spec

## Purpose

UKIP should surface external attention around research entities without becoming a full media monitoring platform. The feature helps users answer:

- Is this entity, concept, author, institution, or cluster receiving attention outside citation metrics?
- Which sources are driving that attention?
- Is the attention new, sustained, or spiking?
- What evidence explains the signal?

## Priority Order

1. **Attention Score MVP**: deterministic score, category, and compact badge.
2. **Source Breakdown**: counts and weighted contribution by source type.
3. **Attention Timeline**: monthly trend and spike detection.
4. **Explanations**: why the score changed or why it matters.
5. **Alerts**: dashboard-ready emerging attention signals.

## MVP Scope

Inputs:

- `domain_id`
- one of `entity_id`, `concept`, `cluster_id`, or `authority_record_id`
- imported external attention observations

Outputs:

```json
{
  "summary": {
    "attention_score": 67,
    "category": "high",
    "total_mentions": 43,
    "active_sources": 4,
    "last_seen_at": "2026-05-15T00:00:00Z"
  },
  "source_breakdown": [],
  "timeline": [],
  "explanations": [],
  "alerts": []
}
```

## Source Taxonomy

- `policy`
- `news`
- `wikipedia`
- `repository`
- `blog`
- `scholarly_web`
- `social_web`
- `other`

## UX Rules

- Never label attention as quality.
- Use badges like `Atencion externa: alta`, not claims like `Impacto alto`.
- Show at most three alerts in the executive dashboard.
- Keep timeline and source breakdown one click away from the badge.
- Prefer compact evidence over long mention lists.

## Acceptance Criteria

- Entity-level attention summary is available via authenticated API.
- Empty data returns a valid zero-score response.
- Source breakdown explains the score composition.
- Timeline shows at least monthly aggregation.
- Alerts are deterministic and tenant-scoped.
- Executive dashboard can show a compact attention card without requiring all future connectors.
