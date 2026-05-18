## Why

UKIP already explains scientific portfolios through citations, concepts, enrichment quality, authority resolution, and temporal analytics. What it does not yet capture is whether an entity is gaining attention outside the bibliographic graph: news, policy, public web references, repositories, or other external mentions.

Altmetric-style products are useful because they make external attention visible, but UKIP should not replicate a full external media intelligence platform. The value for UKIP is narrower: show whether a paper, concept, author, institution, or cluster is receiving external attention, explain why it is changing, and connect that signal to the existing executive dashboard and research analytics.

## What Changes

- **Priority 1: External attention score** - compute a transparent `attention_score` for entities and concept clusters from normalized external mention counts, recency, and source weights.
- **Priority 2: Source breakdown** - expose how the score is composed across a small initial source taxonomy: news, policy, scholarly web, repositories, Wikipedia, blogs, and social/web mentions.
- **Priority 3: Attention timeline** - aggregate attention over time so users can see spikes, persistence, and decay instead of relying on a single number.
- **Priority 4: Spike explanations** - attach compact evidence to score changes: top mentions, source mix changes, and related entities.
- **Priority 5: Emerging attention alerts** - raise deterministic alerts when external attention changes materially relative to the portfolio baseline.

## Non-Goals

- Do not clone Altmetric Explorer or introduce a standalone media monitoring product.
- Do not treat external attention as quality, authority, or citation impact.
- Do not require 20 connectors before the first release.
- Do not add a black-box scoring model.
- Do not ingest private social media or sources that require fragile scraping.
- Do not block the feature on sentiment analysis, geography, or network diffusion.

## Capabilities

### New Capabilities

- `attention-score`: Transparent score and category for records, authors, concepts, institutions, and clusters.
- `attention-sources`: Source taxonomy and weighted source breakdown.
- `attention-timeline`: Daily/monthly temporal aggregation and spike metadata.
- `attention-explanations`: Human-readable evidence for why attention is high or changing.
- `attention-alerts`: Emerging attention alerts for dashboard and notifications.

### Modified Capabilities

- Executive dashboard summary gains an `external_attention` section.
- Entity detail surfaces gain an attention badge and source breakdown.
- Trend/topic analytics can optionally include external attention alongside citations and internal frequency.

## Impact

- **Backend**: New analyzer module, likely `backend/analyzers/external_attention.py`.
- **Backend routers**: New endpoints under `/analyzers/attention/...` or `/external-attention/...`.
- **Models**: Add durable storage for external attention observations or reuse JSON attributes in MVP, depending on implementation phase.
- **Frontend**: Executive dashboard cards, entity detail badges, source breakdown, timeline, and alert list.
- **Engine**: Optional later delegation for batch scoring only after the Python implementation proves useful.
- **Dependencies**: No new heavy dependency required for MVP. Use deterministic Python logic and existing DB models first.
