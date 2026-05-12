## Why

UKIP already ingests scientific metadata (authors, concepts, years, affiliations, citation counts) via its enrichment pipeline and authority resolution layer, but lacks the bibliometric analysis features that researchers expect. Users currently must export data to R/Bibliometrix for trend analysis, author productivity metrics, collaboration networks, and geographic distribution — breaking their workflow. Adding targeted bibliometric analytics directly into UKIP closes this gap without duplicating Bibliometrix's full R-based toolkit, focusing instead on the 4 highest-impact features that leverage data already present in the system.

## What Changes

- **Trend Topics endpoint and UI** — compute frequency slopes per concept over temporal windows, exposing emerging/declining/stable topic classifications via `GET /analyzers/trends/{domain_id}` and a new frontend view.
- **H-index + Author Productivity** — calculate h-index, total publications, total citations, and productivity-over-time per author from `enrichment_citation_count` and authority records; new tab in the authority analysis UI.
- **Co-authorship Network** — introduce `CO_AUTHOR` relationship type in `EntityRelationship`, populate it during import/enrichment, and render it in the existing graph visualizer with degree centrality and community detection.
- **Geographic/Country Analysis** — extract country from affiliation data, aggregate entity counts and citation sums per country, surface as a dashboard heatmap and a dedicated analysis endpoint.

## Capabilities

### New Capabilities
- `trend-topics`: Temporal frequency analysis of concepts — slope computation, trend classification (emerging/declining/stable), configurable time windows.
- `author-productivity`: H-index calculation, per-author publication/citation aggregation, productivity timeline, top-N author ranking.
- `coauthorship-network`: Co-authorship edge extraction from multi-author entities, graph construction with `CO_AUTHOR` relationship type, degree centrality, community detection.
- `geographic-analysis`: Country extraction from affiliations, per-country aggregation (entity count, citation sum, author count), geographic heatmap data.

### Modified Capabilities

## Impact

- **Backend** (`backend/analyzers/`): New modules `trend_analysis.py`, `author_metrics.py`, `geographic.py`; updated `topic_modeling.py` for trend support.
- **Backend** (`backend/routers/analytics.py`): 4+ new endpoints under `/analyzers/`.
- **Models** (`backend/models.py`): `CO_AUTHOR` added to `EntityRelationship.relation_type` vocabulary; possible `country` extracted field on entity or authority record.
- **Frontend**: New pages/tabs for trends, author productivity, geographic analysis; updated graph visualizer for co-authorship.
- **Dependencies**: `numpy` (already present) for slope computation; no new external dependencies required.
- **Data**: Operates on existing `enrichment_concepts`, `enrichment_citation_count`, `attributes_json` (affiliations), and `AuthorityRecord` data — no new data ingestion pipeline needed.
