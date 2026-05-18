## Context

UKIP enriches entities via OpenAlex, storing concepts as flat comma-separated strings in `enrichment_concepts`. OpenAlex concepts have inherent hierarchy (levels 0-5 with ancestor/descendant relationships). This change materializes that hierarchy locally, scoped per tenant corpus, and exposes it through an interactive tree visualization.

This is Fase A of the Domain Analysis RFC (aligned with Hjørland & Albrechtsen's concept-relation layer). It depends on the Ontological Spectrum's LCSH topology primitives (broader/narrower/related) already specified in `docs/ontological_spectrum_spec.md`.

## Goals / Non-Goals

**Goals:**

- Fetch and cache concept ancestor/descendant relationships from OpenAlex Concepts API for concepts already present in the tenant's enriched entities
- Persist concept `level` (0-5) alongside concept names during enrichment
- Expose a concept tree endpoint that returns the hierarchical subgraph with entity counts per node
- Provide a frontend interactive tree/sunburst visualization with drill-down and links to filtered entity views
- Aggressive caching (concepts are stable; refresh weekly at most)

**Non-Goals:**

- Full OpenAlex concept taxonomy download (only corpus-relevant concepts)
- Epistemic classification of concepts (Fase B)
- Domain health metrics or convergence scoring (Fase C/D)
- Editing or manually creating concept relationships
- Real-time concept hierarchy updates during enrichment (batch materialization is sufficient)

## Decisions

1. **Storage**: New `concept_nodes` table (id, openalex_id, display_name, level, parent_id FK self-referential, entity_count, last_fetched_at). Lightweight relational tree — no graph DB needed at this scale.

2. **Materialization trigger**: On-demand via `POST /analytics/concepts/{domain_id}/materialize` (admin+). Also callable from enrichment bulk completion hook. Idempotent — upserts nodes.

3. **API fetching strategy**: Start from leaf concepts (those in `enrichment_concepts`), walk up ancestors via OpenAlex `/concepts/{id}` endpoint. Use httpx async with polite-pool (max 5 concurrent, 100ms delay). Cache raw responses in `concept_cache/` directory (JSON files keyed by OpenAlex concept ID).

4. **Tree endpoint**: `GET /analytics/concepts/{domain_id}/tree` returns nested JSON. Optional `?root_level=N` to start from a specific depth. Each node includes `{id, name, level, entity_count, children: [...]}`.

5. **Concept detail**: `GET /analytics/concepts/{domain_id}/{concept_id}` returns node metadata + list of entities tagged with that concept (paginated).

6. **Frontend**: Single page at `/analytics/concepts` with:
   - Collapsible tree view (default) showing hierarchy with entity count badges
   - Sunburst toggle for proportional visualization
   - Click node → filters entity table to that concept
   - Uses existing Recharts (Treemap) + custom tree component (no new dependencies)

7. **Enrichment change**: When persisting enrichment results, also store concept OpenAlex IDs (available in the API response) in `attributes_json.enrichment_concept_ids` to enable direct lookups without fuzzy matching.

8. **Domain scoping**: The `concept_nodes` table includes a `domain` column. Each domain gets its own materialized subgraph based on entities with that domain value.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| OpenAlex rate limiting (polite pool = 10 req/s for unauthenticated) | Aggressive file-based caching; batch materialization off-peak; concept hierarchies are very stable |
| Concept name mismatch between stored strings and OpenAlex canonical names | Store OpenAlex concept IDs during enrichment; fallback to fuzzy match on display_name for legacy data |
| Large corpus = many leaf concepts = deep ancestry walks | Cap at 2000 unique concepts per materialization run; paginate; level-0 concepts are few (~20) so tree stays manageable |
| Self-referential FK migrations on SQLite | Use nullable parent_id; SQLite handles self-referential FKs fine with proper pragma |
| Frontend performance with large trees | Virtualize tree nodes; collapse below level 3 by default; lazy-load children on expand |
