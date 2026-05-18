## Context

UKIP has strong quantitative analytics (topic modeling, co-occurrence PMI, correlation analysis, OLAP cube) but no qualitative lens. Fase A (concept hierarchy) established the hierarchical structure of concepts from OpenAlex. Fase B adds epistemic classification — tagging each enriched entity with paradigm affinity scores derived from text matching against configurable indicators.

The existing architecture provides all necessary inputs: `enrichment_concepts` (comma-separated), `abstract` (from attributes_json via enrichment), `document_type`, and `journal` fields on `RawEntity`. The classification output goes into `attributes_json.epistemic_profile` — no new database tables are needed.

Domain YAML files (`backend/domains/*.yaml`) define the schema via `DomainSchema` in `schema_registry.py`. The epistemology section is added as an optional key that the registry parses but ignores when absent, preserving backward compatibility.

## Goals / Non-Goals

**Goals:**
- Classify enriched entities by epistemic paradigm using term-frequency matching (no external NLP)
- Store paradigm affinity as a normalized score vector in `attributes_json.epistemic_profile`
- Provide batch classification for existing entities and auto-classification on enrichment
- Surface paradigm distribution via API endpoints and a frontend analytics widget
- Add `paradigm` as an OLAP dimension for cross-tabulation
- Make the system configurable per domain via YAML (paradigms, indicators, evidence hierarchy)

**Non-Goals:**
- LLM-based or embedding-based classification (v2 upgrade path, not this phase)
- Modifying the enrichment pipeline itself (only adding a post-enrichment hook)
- Implementing evidence hierarchy scoring (defined in YAML but analytics deferred to Fase D)
- Cross-domain paradigm comparison (Fase C scope)
- New database tables or migrations

## Decisions

### 1. Scoring approach: weighted term-frequency matching

**Decision:** Score each entity against each paradigm by counting indicator term hits in abstract + concepts + document_type, normalized to [0, 1].

**Rationale:** Text matching with curated indicator lists is transparent, fast, debuggable, and requires no external dependencies. The RFC acknowledges this is "imprecise by text matching" (Risk #1) but sufficient as a v1 — the indicator lists can be tuned by domain experts via YAML without code changes.

**Alternatives considered:**
- TF-IDF + cosine similarity: Heavier, requires corpus-level statistics, overkill for curated terms
- LLM classification: Accurate but slow/expensive for batch processing, deferred to v2
- Embedding similarity: Requires vector store, adds dependency complexity

**Scoring formula:**
```
For entity E and paradigm P:
  term_score = count(P.indicators.terms found in E.abstract) / len(P.indicators.terms)
  type_score = 1.0 if E.document_type in P.indicators.document_types else 0.0
  journal_score = 1.0 if E.journal in P.indicators.journals_affinity else 0.0

  raw_score = 0.6 * term_score + 0.25 * type_score + 0.15 * journal_score
```
Scores are normalized across paradigms so they sum to 1.0. If no paradigm scores > 0, the entity is marked `unclassified`.

### 2. Storage: attributes_json (no new table)

**Decision:** Store epistemic profile in `attributes_json.epistemic_profile` as a dict.

**Format:**
```json
{
  "epistemic_profile": {
    "paradigms": {"empiricist": 0.72, "constructivist": 0.18, "critical": 0.10},
    "dominant": "empiricist",
    "classified_at": "2026-05-18T12:00:00Z"
  }
}
```

**Rationale:** Follows the existing pattern for enrichment metadata (e.g., `enrichment_concept_ids`, `enrichment_authors`, `enrichment_failure`). Avoids schema migration. The OLAP layer already reads attributes_json.

### 3. DomainSchema extension: optional epistemology key

**Decision:** Add `EpistemologyConfig` as an optional field on `DomainSchema`. The schema registry parses it when present in YAML, ignores when absent.

**Rationale:** Keeps backward compatibility. Non-science domains don't need epistemology. The YAML structure mirrors the RFC Section 3.1 exactly.

### 4. Classification trigger: batch endpoint + post-enrichment hook

**Decision:** Two classification paths:
1. `POST /analytics/epistemic/{domain_id}/classify` — batch classifies all entities missing a profile (admin+)
2. Post-enrichment hook in `enrichment_worker.py` — auto-classifies on successful enrichment

**Rationale:** Batch handles existing entities; hook handles new ones. Both call the same classifier function.

### 5. OLAP integration: derive paradigm column from attributes_json

**Decision:** In `olap.py._load_domain_df()`, extract `dominant` paradigm from `attributes_json.epistemic_profile.dominant` as a new column, making it available as an OLAP dimension.

**Rationale:** Minimal change — the OLAP layer already parses attributes_json for other fields. Adding one more extraction keeps the pattern consistent.

### 6. Frontend: new sub-page under /analytics/epistemic

**Decision:** New page at `frontend/app/analytics/epistemic/page.tsx` with:
- Paradigm distribution donut chart (Recharts PieChart)
- Temporal evolution area chart (paradigm % by year)
- Top entities per paradigm table
- Link from analytics overview page

**Rationale:** Follows the existing pattern of analytics sub-pages (topics, concepts, olap).

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Text matching produces noisy scores for short/missing abstracts | Skip classification when abstract is absent or < 50 chars; mark as `unclassified` |
| Paradigm indicators biased toward English-language terms | Document as limitation; i18n indicators can be added per-domain in v2 |
| OLAP dimension cardinality is low (3-4 paradigms) | Acceptable — low cardinality is actually ideal for cross-tab dimensions |
| Batch classification of large corpora is slow | Process in chunks of 500; use synchronous DB reads (no async needed for text matching) |
| Journal affinity lists become stale | Lists are in YAML; domain admins can update without code changes |
