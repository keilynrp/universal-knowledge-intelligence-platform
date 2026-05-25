# Application Service Architecture

## Service Boundaries

UKIP is organized as a modular monolith. Domain logic lives in routers and services with clear boundaries.

```
┌───────────────────────────────────────────────────────────────┐
│                        API Layer                               │
│  backend/routers/*.py (46 routers)                            │
│  FastAPI dependency injection, auth, rate limiting             │
└──────┬──────┬──────┬──────┬──────┬──────┬──────┬─────────────┘
       │      │      │      │      │      │      │
       ▼      ▼      ▼      ▼      ▼      ▼      ▼
  Ingest  Enrich  Recon  Analyt  Report  RAG   Auth
```

### 1. Ingestion Service

**Routers:** `ingest`, `api_import`, `scientific_import`, `scheduled_imports`
**Responsibility:** Accept data from CSV/Excel/BibTeX/RIS uploads, REST APIs, and commerce adapters. Parse, validate, persist as `RawEntity` records.

**Key contracts:**
- Upload: max 20 MB, returns entity count
- Source profiling: `backend/services/source_profiler.py` analyzes field types and semantic roles
- Entities tagged with `source` column (user/demo/adapter name)

### 2. Enrichment Service

**Routers:** `entities` (enrich endpoints), `enrichment_schedule`
**Workers:** `enrichment_worker.py`, `enrichment_scheduler.py`
**Responsibility:** Enrich entities via external APIs (OpenAlex, Web of Science, Google Scholar). Circuit-breaker protected.

**Key contracts:**
- Enrichment adds to `enrichment` layer (never overwrites `source`)
- Worker claims entities atomically (`UPDATE WHERE status='pending'`)
- Circuit breaker per provider (3/5 failures → 60-120s open)

### 3. Reconciliation & Authority Service

**Routers:** `authority`, `disambiguation`, `entity_linker`
**Services:** `authority/`, `institution_reconciliation.py`, `geographic_reconciliation.py`, `authority_candidate_extraction.py`, `authority_promotion.py`
**Responsibility:** Resolve entities against authoritative registries. Deduplicate. Promote to canonical layer.

**Key contracts:**
- 5 external resolvers: ORCID, ROR, Wikidata, VIAF, OpenAlex (parallel, 12s timeout)
- Weighted scoring engine (identifiers 0.35, name 0.25, affiliation 0.20, reserved 0.20)
- Promotion requires conflict check; auto-accept at confidence >= threshold
- Layer boundaries enforced: authority never overwrites enrichment or source

### 4. Analytics & Intelligence Service

**Routers:** `analytics`, `quality`, `nlq`, `context`, `external_attention`
**Services:** `topic_modeling.py`, `correlation.py`, `decision_readout.py`, `audience_presets.py`
**Responsibility:** KPI dashboards, topic modeling (PMI co-occurrence), field correlation (Cramer's V), OLAP cube queries, decision readouts.

**Key contracts:**
- Dashboard summary: entity stats, enrichment coverage, timeline, top concepts
- OLAP: DuckDB queries with safe identifier validation
- Decision readout: derived from dashboard metrics, audience-framed

### 5. Reporting & Export Service

**Routers:** `reports`, `artifacts`, `scheduled_reports`, `graph_export`, `sales_deck`
**Services:** `evidence_traceability.py`, `jsonld_exporter.py`, `excel_exporter.py`
**Responsibility:** Generate reports (HTML/PDF/Excel), JSON-LD linked-data exports, graph exports.

**Key contracts:**
- PDF via WeasyPrint (lazy-imported, 501 if not installed)
- Excel: branded 4-sheet workbook (Summary, Entities, Concepts, Harmonization)
- JSON-LD: schema.org/BIBFRAME/EDM/DCAT vocabulary alignment
- Evidence traceability panels for exported briefs

### 6. RAG & AI Service

**Routers:** `ai_rag`, `agentic_chat`
**Services:** `rag_skill_registry.py`, `rag_skill_router.py`, `rag_skill_execution.py`, `rag_skills_library.py`
**Responsibility:** Vector search (ChromaDB), skill-assisted RAG, agentic chat, GenAI governance.

**Key contracts:**
- Skills: advisory (evidence-grading, citation-grounding, stakeholder-briefing) vs governed (candidates)
- Routing: direct_answer / single_skill / plan_candidate / policy_block
- GenAI governance: confidence + evidence required, AI badge always shown
- All invocations audited with provenance

### 7. Auth & Platform Service

**Routers:** `auth_users`, `platform_auth_settings`, `api_keys`, `organizations`, `onboarding`
**Services:** `auth.py`, `bootstrap.py`
**Responsibility:** JWT authentication, RBAC (viewer/editor/admin/super_admin), user management, API keys, SSO.

**Key contracts:**
- `require_role(*roles)` dependency factory
- Account lockout after 5 failed attempts (15 min)
- API keys with scope control
- Audit middleware logs all mutating calls

## Integration Contracts Between Services

| Producer | Consumer | Contract |
|----------|----------|----------|
| Ingestion | Enrichment | `RawEntity` with `enrichment_status='pending'` |
| Enrichment | Reconciliation | `attributes_json` with enriched fields |
| Reconciliation | Authority | `AuthorityRecord` with candidates |
| Authority | Analytics | Confirmed authority records in entity detail |
| Analytics | Reporting | Dashboard summary dict |
| Reporting | Export | Evidence panels, JSON-LD documents |
| RAG | GenAI Governance | `GenAIOutput` validated before persistence |
| All mutating | Audit | `AuditMiddleware` captures method + path + user |

## Service Review Checklist

When adding a new service or modifying boundaries:

- [ ] Does it belong to an existing service boundary or need a new one?
- [ ] Are layer boundaries respected (source/enrichment/canonical/authority)?
- [ ] Is auth enforced (`require_role` or `get_current_user`)?
- [ ] Are inputs validated (Pydantic schemas, path/query param bounds)?
- [ ] Is the GenAI governance contract followed for AI outputs?
- [ ] Is an ADR needed (new service boundary, canonical rule, strategic dependency)?
- [ ] Are tests written (unit + integration)?
