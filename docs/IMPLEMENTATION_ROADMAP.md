# Implementation Roadmap — Architecture Contract Tasks

Derived from the 11 governance specs archived 2026-05-23.
Ordered by dependency chain, technical foundation, and business value.

---

## Phase 1: Data Foundation (No Dependencies) ✅ COMPLETE

These specs have zero upstream dependencies and unlock everything else.

### 1.1 Scientific Affiliation Contract ✅ (pre-existing)
**Change:** scientific-affiliation-normalization
**Type:** NEW (data schema)
**Effort:** S
**Status:** Already implemented in `backend/schemas_enrichment.py`

- [x] Define `CanonicalAffiliation` Pydantic model (name, ror, openalex_id, country_code, type, lineage)
- [x] Define `AuthorAffiliation` Pydantic model (author name, orcid, provider_author_id, position, institutions[])
- [x] Add optional `canonical_affiliations` and `author_affiliations` to `EnrichedRecord`
- [x] Preserve backward-compatible `affiliations` text list
- [x] Tests: empty, text-only, structured, ROR-backed, OpenAlex-only records

### 1.2 Geographic Entity Model ✅ (2026-05-24)
**Change:** geographic-entity-semantic-layer
**Type:** NEW (database model)
**Effort:** M
**Files:** `backend/models.py` (GeographicEntity), `backend/services/geographic_entities.py`, `tests/test_geographic_entities.py` (30 tests)

- [x] Create `GeographicEntity` model: id, type (country/region/city/campus/address/spatial_area/unknown), name, parent_id, coordinates, country_code (ISO 3166-1), geonames_id, wikidata_id, osm_id, aliases (JSON), geometry (GeoJSON), provenance
- [x] Implement ID normalization helpers: ISO country validation, GeoNames ID, Wikidata QID, OSM ID
- [x] Implement hierarchy traversal (parent_id chain)
- [x] Implement alias support (multilingual/variant names)
- [x] Tests: valid country, partial entity, invalid ISO, hierarchy, schema validation

### 1.3 ROR Registry Adapter ✅ (pre-existing)
**Change:** institution-affiliation-reconciliation
**Type:** NEW (external API adapter)
**Effort:** S
**Status:** Already implemented in `backend/services/institution_reconciliation.py` (RORAdapter class)

- [x] Create `RORRegistryAdapter` class
- [x] Normalize ROR identifier (URL `https://ror.org/xxxxx` or bare ID)
- [x] Implement lookup by ROR ID (full record: name, aliases, country, type, links, external IDs)
- [x] Implement search by name+country (ranked candidates)
- [x] Graceful HTTP error handling (no crashes on API unavailability)
- [x] Tests: URL normalization, lookup, search, API error handling

### 1.4 Source Profiling Contract ✅ (2026-05-24)
**Change:** canonical-semantic-data-governance
**Type:** NEW (service + model)
**Effort:** L
**Files:** `backend/models.py` (SourceProfile), `backend/services/source_profiler.py`, `tests/test_source_profiler.py` (32 tests)

- [x] Create `SourceProfile` model: source_id, field_profiles (JSON), semantic_candidates (JSON), candidate_identifiers (JSON), inferred_types, sparsity_map
- [x] Create `SourceProfiler` service:
  - Analyze field names, inferred types, sparsity, sample values, distributions
  - Identify semantic roles: Person, Organization, Place, Concept, Publication, Dataset
  - Handle flat CSV, paginated REST, OpenAlex Works, Crossref Works payloads
- [ ] API: `POST /sources/profile`, `GET /sources/{id}/profile`, `GET /sources/{id}/candidates` *(deferred to Phase 2)*
- [ ] Frontend: import wizard integration (display profile summary after upload) *(deferred to Phase 2)*
- [x] Tests: CSV, REST, OpenAlex, Crossref, identifier-sparse scenarios

### 1.5 Source Terminology Contract ✅ (2026-05-24)
**Change:** entity-provenance-layering
**Type:** NEW (i18n + helpers)
**Effort:** XS
**Files:** `backend/services/source_terminology.py`, `frontend/app/i18n/translations.ts`, `tests/test_source_terminology.py` (19 tests)

- [x] Define source type enum: `ingestion_source`, `enrichment_provider`, `authority_source`
- [x] Create `get_source_label(field_name, value_type)` helper
- [x] EN/ES translations: "Ingestion source", "Enrichment provider", "Authority source"
- [x] Section headers: "Original ingestion", "UKIP normalized identity", "External enrichment", "Authority and audit"
- [x] Tests: distinct labels for ingestion/enrichment/authority

### 1.6 RAG Skill Registry ✅ (2026-05-24)
**Change:** rag-skill-orchestration
**Type:** NEW (backend service)
**Effort:** M
**Files:** `backend/services/rag_skill_registry.py`, `backend/skills/default_skills.yaml`, `tests/test_rag_skill_registry.py` (18 tests)

- [x] Define `SkillDefinition` schema: skill_id, version, description, input_schema, output_schema, allowed_evidence_types, governance_level (advisory/review_required/governed_write_candidate), timeout_ms, audit_category
- [x] Implement registry loading from static YAML config
- [x] Implement allowlist enforcement: tenant, domain, feature flag scoping
- [x] Classify skills: advisory (summarize/grade) vs governed (produce candidates)
- [x] Tests: invalid definition rejected, disabled skill not routable, allowlist enforcement

---

## Phase 2: Core Services (Depends on Phase 1) ✅ COMPLETE

### 2.1 OpenAlex Affiliation Mapping ✅ (pre-existing)
**Change:** scientific-affiliation-normalization
**Depends on:** 1.1
**Status:** Already implemented in `backend/adapters/enrichment/openalex.py`

- [x] Extend OpenAlex adapter to parse `authorships[].institutions[]`
- [x] Extract institution display_name, ROR IDs, country_code from metadata
- [x] Build `author_affiliations` preserving author-to-institution relationships
- [x] Build `canonical_affiliations` deduplicated by ROR > OpenAlex ID > normalized name
- [x] Populate legacy `affiliations` text for backward compatibility
- [x] Tests: multiple authors, duplicate institutions, ROR-backed, no-ROR institutions

### 2.2 Affiliation Persistence Contract ✅ (2026-05-24)
**Change:** scientific-affiliation-normalization
**Depends on:** 1.1, 2.1
**Status:** enrichment_worker already persists; `_ingest_records` in api_import now also persists
**Files:** `backend/routers/api_import.py` (updated)

- [x] Update `_ingest_records()` to persist `canonical_affiliations` and `author_affiliations` into `attributes_json`
- [x] Preserve legacy `affiliation`/`affiliations` keys for geographic fallback
- [x] Handle Pydantic v2 model dumps and plain dicts
- [x] Create helper to read normalized affiliation metadata from `attributes_json` (in `scientific_affiliations.py`)
- [x] Tests: EnrichedRecord → RawEntity.attributes_json persistence (in existing test suite)

### 2.3 ROR-Ready Institution Identifiers ✅ (pre-existing)
**Change:** scientific-affiliation-normalization
**Status:** Already implemented in `backend/services/scientific_affiliations.py`

- [x] ROR normalization helper (URL or bare ID → stable format)
- [x] Extract institution candidates from persisted affiliations
- [x] Deduplicate by ROR (same ROR = one candidate)
- [x] Mark ROR-unresolved institutions with available identifiers
- [x] Tests: ROR URL normalization, extraction, deduplication

### 2.4 Geographic Reconciliation Service ✅ (2026-05-24)
**Change:** geographic-entity-semantic-layer
**Depends on:** 1.2
**Files:** `backend/services/geographic_reconciliation.py`, `tests/test_geographic_reconciliation.py` (17 tests)

- [x] Create `GeographicReconciliationService`
- [x] ISO country normalization as primary path (confidence 1.0)
- [x] Common country name mapping ("United States" → US, "Germany" → DE) — 100+ mappings
- [x] Variant/alias matching (case-folding, diacritic stripping)
- [x] Extract candidates from structured affiliations (country/city tokens)
- [x] Extract candidates from imported columns (country, city, region, latitude/longitude)
- [x] Confidence scoring: 1.0 exact ISO, 0.95 exact name, 0.85 alias, 0.5 ambiguous
- [x] Preserve evidence: original value, source field, extraction method
- [x] Tests: ISO, common name, variant, ambiguous (e.g. "Georgia"), coordinates

### 2.5 Institution Reconciliation Service ✅ (pre-existing)
**Change:** institution-affiliation-reconciliation
**Status:** Already implemented in `backend/services/institution_reconciliation.py`

- [x] Create `InstitutionReconciliationService`
- [x] ROR ID inputs → deterministic high-confidence match
- [x] Name+country inputs → registry search → ranked candidates
- [x] Score breakdown: name_match, country_match, alias_match, registry_source
- [x] Detect ambiguous/review-level candidates (multiple similar scores)
- [x] Handle ROR API unavailability gracefully
- [x] Tests: ROR resolve, name+country search, ambiguous, API error

### 2.6 Entity Provenance Layering ✅ (2026-05-24)
**Change:** entity-provenance-layering
**Depends on:** 1.5
**Files:** `backend/services/entity_provenance.py`, `tests/test_entity_provenance.py` (9 tests)

- [x] `import_batch_id` already exists on RawEntity
- [x] Create `EntityDetailLayered` schema grouping fields into 4 layers:
  - `original_ingestion` (source fields)
  - `normalized_identity` (canonical fields)
  - `external_enrichment` (enrichment fields)
  - `authority_audit` (authority records)
- [x] Implement `_assign_field_to_layer(field_name)` helper (in source_terminology.py)
- [ ] Extend `GET /entities/{id}` with `detail_layered` *(deferred to Phase 3 API integration)*
- [ ] Refactor `EntityDetail.tsx` into 4 visual sections *(deferred to frontend sprint)*
- [x] Tests: separation, grouping, authority display, ingestion-only, attributes_json expansion

### 2.7 Entity Detail Null Semantics ✅ (2026-05-24)
**Change:** entity-provenance-layering
**Depends on:** 2.6
**Files:** `backend/services/null_semantics.py`, `frontend/app/i18n/translations.ts`, `tests/test_null_semantics.py` (11 tests)

- [x] Implement `compute_field_null_reason(entity, field_name)` → `not_provided | pending_normalization | unresolved_enrichment | not_applicable | unknown`
- [x] Extend entity detail serializer with null_reason_code + display_copy
- [x] EN/ES translations for all null-reason states
- [ ] Update `EntityDetailField.tsx` to display null-reason copy *(deferred to frontend sprint)*
- [x] Tests: uploaded without identifiers, enriched missing DOI, legacy record

### 2.8 RAG Skill Router ✅ (2026-05-24)
**Change:** rag-skill-orchestration
**Depends on:** 1.6
**Files:** `backend/services/rag_skill_router.py`, `tests/test_rag_skill_router.py` (10 tests)

- [x] Define router input contract: query, evidence summary, domain scope, user role, tenant, available skills
- [x] Implement routing decisions: direct_answer, single_skill, plan_candidate, policy_block
- [x] Require confidence + policy reason in every decision
- [x] Role-based skill eligibility (editor/admin skills not available to viewers)
- [x] Domain-scoped skill filtering
- [x] Audit recording for every routing decision
- [x] Tests: direct RAG, skill-assisted, insufficient evidence, policy-blocked

### 2.9 RAG Skill Execution ✅ (2026-05-24)
**Change:** rag-skill-orchestration
**Depends on:** 1.6, 2.8
**Files:** `backend/services/rag_skill_execution.py`, `tests/test_rag_skill_execution.py` (12 tests)

- [x] Define `SkillInvocation` record: query_id, skill_id, version, input evidence, output, status, confidence, provenance, timing, review_status
- [x] Validate skill input/output against declared schemas
- [x] Enforce timeout (terminate + mark failed)
- [x] Safe fallback to direct RAG on failure
- [x] Prevent skills from mutating canonical data directly (read-only handlers)
- [x] Persist audit events for every invocation (success, failed, policy-blocked)
- [x] Tests: completed, failed, timed-out, review-required invocations

---

## Phase 3: Integration & Authority (Depends on Phase 2) ✅ COMPLETE

### 3.1 Mapping Suggestion Contract ✅ (2026-05-24)
**Change:** canonical-semantic-data-governance
**Depends on:** 1.4, 2.6
**Type:** NEW (model + service)
**Effort:** L
**Files:** `backend/services/mapping_suggestions.py`, `tests/test_mapping_suggestions.py` (24 tests)

- [x] Create `MappingSuggestion` dataclass: source_field, canonical_target, confidence, evidence_samples, status (auto_acceptable/review_required/accepted/rejected/superseded), reviewer_id, reviewed_at, rationale
- [x] Create `MappingSuggestionService`:
  - `generate_suggestions(source_profile)` → suggestions with confidence scoring
  - `accept_suggestion(id, reviewer)` → apply mapping, record timestamp
  - `reject_suggestion(id, rationale, reviewer)` → preserve suggestion + rationale
  - `check_reappearance(profile_change)` → suppress duplicate suggestions
  - `supersede_suggestion(old_id, new_id)` → mark old superseded
- [ ] API (editor+): `GET /mapping-suggestions`, `POST /{id}/accept`, `POST /{id}/reject` *(deferred to API integration sprint)*
- [ ] Frontend: `MappingSuggestionReview.tsx` *(deferred to frontend sprint)*
- [x] Tests: accept/reject/review-required/supersede lifecycle

### 3.2 Institution Authority Records ✅ (2026-05-24)
**Change:** institution-affiliation-reconciliation
**Depends on:** 2.5
**Type:** NEW (model + persistence)
**Effort:** S
**Files:** `backend/services/institution_authority.py`, `tests/test_institution_authority.py` (20 tests)

- [x] Create `InstitutionAuthority` dataclass: canonical_name, ror_id, openalex_id, aliases (JSON), country, confidence, status, source_identifiers
- [x] Implement accept logic (create/link authority record)
- [x] Implement reusability (check existing by ROR/OpenAlex before duplicate)
- [x] Tests: ROR-backed accepted, OpenAlex-only, reuse of existing record

### 3.3 Institution Affiliation Review ✅ (2026-05-24)
**Change:** institution-affiliation-reconciliation
**Depends on:** 2.5, 3.2
**Type:** NEW (review logic embedded in institution_authority.py)
**Effort:** M

- [x] Accept/reject logic in `InstitutionAuthorityStore.accept()` / `.reject()`
- [x] List with status filter: `list_records(status="pending")`
- [ ] Review queue API endpoint *(deferred to API integration sprint)*
- [ ] Review UI *(deferred to frontend sprint)*
- [x] Tests: accept, reject, status filtering (in test_institution_authority.py)

### 3.4 Geographic Relationship Materialization ✅ (2026-05-24)
**Change:** geographic-entity-semantic-layer
**Depends on:** 1.2, 2.4, 2.5
**Type:** NEW (relationship service)
**Effort:** M
**Files:** `backend/services/geographic_relationships.py`, `tests/test_geographic_relationships.py` (14 tests)

- [x] Define relationship types: `located_in`, `associated_with`, `covers_region`, `affiliated_in`, `held_at`, `contained_in`
- [x] Materialize `organization located_in` from institution reconciliation (ROR country → country entity)
- [x] Materialize `publication associated_with` from author affiliations (multi-country deduplication)
- [x] Materialize `dataset covers_region` from spatial coverage
- [x] Include confidence + evidence metadata on all relationships
- [x] Tests: located_in with ROR, associated_with multi-country, covers_region, provenance

### 3.5 Authority Candidate Extraction ✅ (2026-05-24)
**Change:** authority-enrichment-bridge
**Depends on:** 2.2, 2.3, 2.4
**Type:** NEW (extraction service)
**Effort:** L
**Files:** `backend/services/authority_candidate_extraction.py`, `tests/test_authority_candidate_extraction.py` (17 tests)

- [x] Create `AuthorityCandidateExtractor` class
- [x] Person candidates: enriched authors (name, ORCID, affiliation) + context → candidates with confidence
- [x] Institution candidates: structured affiliations (name, ROR, OpenAlex, country) → candidates
- [x] Identifier candidates: DOI, ORCID, ROR → candidates with regex validation
- [x] Place candidates: country codes from affiliations → candidates
- [x] Venue candidates: journal, ISSN → candidates
- [x] Concept candidates: enriched concepts → candidates
- [x] Source-only extraction (no enrichment): lower confidence, mark as `source` origin
- [x] Deduplication across source + enrichment layers (by dedup_key, highest confidence wins)
- [x] Tests: enriched, source-only, deduplication, sparse evidence

### 3.6 Authority Readiness Status ✅ (2026-05-24)
**Change:** authority-enrichment-bridge
**Depends on:** 3.5
**Type:** NEW (state machine)
**Effort:** M
**Files:** `backend/services/authority_readiness.py`, `tests/test_authority_readiness.py` (14 tests)

- [x] Define readiness enum: not_started, source_candidates_ready, enrichment_candidates_ready, review_required, partially_resolved, resolved, stale, failed
- [x] Create readiness tracking: per-dataset/domain with per-family breakdown (person, institution, identifier, place, venue, concept)
- [x] Per-family counts: extracted, resolved, review_required, rejected, failed, stale
- [x] Stale detection: evidence changes after extraction → mark candidates stale
- [ ] API: `GET /authority/readiness/{dataset_id}` *(deferred to API integration sprint)*
- [x] Tests: state transitions, stale detection, accumulation

### 3.7 Authority Canonical Promotion ✅ (2026-05-24)
**Change:** authority-enrichment-bridge
**Depends on:** 3.5, 3.6
**Type:** NEW (promotion service)
**Effort:** L
**Files:** `backend/services/authority_promotion.py`, `tests/test_authority_promotion.py` (17 tests)

- [x] Define promotion payload: entity_type, label, identifiers, confidence, evidence_refs, reviewer/auto-policy
- [x] Preserve source + enrichment layers (never overwrite)
- [x] Conflict detection: same identifier different label → conflict status
- [x] Auto-accept rules: governed policy + confidence threshold (configurable)
- [x] Rejection persistence + audit trail (not recreated unless evidence changes)
- [x] Tests: acceptance, conflict, auto-accept, rejection prevention, listing

### 3.8 Canonical Model Authority Boundary ✅ (2026-05-24)
**Change:** canonical-semantic-data-governance
**Depends on:** 2.6, 3.7
**Type:** REFACTOR (layer enforcement)
**Effort:** M
**Files:** `backend/services/layer_boundaries.py`, `tests/test_layer_boundaries.py` (31 tests)

- [x] Implement `enforce_layer_boundaries()` validation:
  - Enrichment apply cannot overwrite source or canonical
  - Authority resolution cannot overwrite enrichment
  - Canonical promotion cannot destroy source
  - Re-ingestion versions source layer without overwriting canonical/authority
- [x] Rollback logic: enrichment removal doesn't affect canonical/authority
- [x] Tests: original survives promotion, canonical survives authority, authority survives enrichment, all layers queryable

---

## Phase 4: UX, Exports & Intelligence (Depends on Phase 3) ✅ COMPLETE

### 4.1 Authority Review UX ✅ (2026-05-24)
**Change:** authority-enrichment-bridge
**Depends on:** 3.5, 3.6, 3.7
**Type:** NEW (i18n + contracts)
**Effort:** M
**Files:** `frontend/app/i18n/translations.ts` (EN+ES)

- [x] EN/ES translations for readiness states (8), families (6), origin labels (4), review actions (5)
- [ ] Authority readiness card component *(deferred to frontend sprint)*
- [ ] Review queue UI *(deferred to frontend sprint)*

### 4.2 RAG Skill UX ✅ (2026-05-24)
**Change:** rag-skill-orchestration
**Depends on:** 2.8, 2.9
**Type:** NEW (i18n + contracts)
**Effort:** M
**Files:** `frontend/app/i18n/translations.ts` (EN+ES)

- [x] EN/ES translations: skill statuses (4), governance labels (3), review CTA, policy explanation
- [ ] Skill badge component *(deferred to frontend sprint)*
- [ ] Expandable panel component *(deferred to frontend sprint)*

### 4.3 Decision Readout Builder ✅ (2026-05-24)
**Change:** research-stakeholder-executive-demo
**Depends on:** 2.6 (provenance data)
**Type:** NEW (backend service)
**Effort:** M
**Files:** `backend/services/decision_readout.py`, `tests/test_decision_readout.py` (18 tests)

- [x] Define `DecisionReadout` dataclass: corpus_size, enrichment_coverage, authority_coverage, quality_score, known_signals, emerging_signals, confidence_level, missing_data, recommendations
- [x] `DecisionReadoutBuilder.build(dashboard, audience)` derives readout from dashboard summary
- [x] Safe fallbacks: empty corpus, partial enrichment, missing concepts, missing timeline
- [x] Confidence computation from coverage metrics
- [x] Recommendation generation with evidence refs
- [x] Tests: complete, partial, empty dashboard payloads

### 4.4 Stakeholder Demo Flow ✅ (2026-05-24)
**Change:** research-stakeholder-executive-demo
**Depends on:** 4.3
**Type:** NEW (backend integration ready)
**Effort:** M

- [x] Decision readout builder supports audience parameter
- [x] StakeholderBriefingSkill generates narrative from readout
- [ ] Frontend `?mode=stakeholder-demo` walkthrough *(deferred to frontend sprint)*
- [ ] localStorage dismiss/reset *(deferred to frontend sprint)*

### 4.5 Audience Presets ✅ (2026-05-24)
**Change:** research-stakeholder-executive-demo
**Depends on:** 4.3, 4.4
**Type:** NEW (backend service)
**Effort:** S
**Files:** `backend/services/audience_presets.py`, `tests/test_audience_presets.py` (12 tests)

- [x] Define 5 presets: leadership, research_office, investigator, innovation_transfer, evaluator
- [x] `get_preset(audience)` with fallback to leadership
- [x] `apply_framing(readout_dict, audience)` adds audience metadata + emphasis markers
- [x] EN/ES labels, descriptions, CTAs for all presets
- [x] Default: leadership
- [x] EN/ES translations in i18n file
- [x] Tests: audience switching, framing changes, values unchanged

### 4.6 Evidence Traceability UI ✅ (2026-05-24)
**Change:** research-stakeholder-executive-demo
**Depends on:** 4.3
**Type:** NEW (backend service)
**Effort:** M
**Files:** `backend/services/evidence_traceability.py`, `tests/test_evidence_traceability.py` (10 tests)

- [x] `EvidenceTraceabilityService.build_panels(recommendations, entities, concepts, quality_metrics)` → evidence panels
- [x] 5 evidence types: benchmark, concept, entity, quality, enrichment
- [x] Graceful fallback copy when evidence unavailable
- [x] `build_appendix(panels)` for exported PDF/HTML briefs
- [x] EN/ES translations for evidence types
- [x] Tests: evidence panel rendering, fallback copy, appendix generation

### 4.7 Linked-Data Output Governance ✅ (2026-05-24)
**Change:** canonical-semantic-data-governance
**Depends on:** 3.4, 3.7, 3.8
**Type:** NEW (export service)
**Effort:** L
**Files:** `backend/exporters/jsonld_exporter.py`, `tests/test_jsonld_exporter.py` (22 tests)

- [x] `JSONLDExporter.export_entity(entity, vocabulary)` → JSON-LD document
- [x] Alignment mappings: BIBFRAME (bf:Work), EDM (edm:ProvidedCHO), schema.org (ScholarlyArticle/Dataset/Person/etc), DCAT (dcat:Dataset)
- [x] Geographic linked-data: `export_geographic()` → schema.org Place with GeoCoordinates
- [x] Authority sameAs URIs (Wikidata, VIAF, ORCID)
- [x] Affiliation export with ROR identifiers
- [x] Provenance metadata (sdPublisher, isBasedOn)
- [ ] API: `GET /exports/{entity_id}/jsonld` *(deferred to API integration sprint)*
- [x] Tests: schema.org, BIBFRAME, EDM, DCAT, geographic, authority, affiliations

### 4.8 Initial RAG Skills ✅ (2026-05-24)
**Change:** rag-skill-orchestration
**Depends on:** 2.9
**Type:** NEW (skill implementations)
**Effort:** M
**Files:** `backend/services/rag_skills_library.py`, `tests/test_rag_skills_library.py` (22 tests)

- [x] `EvidenceGradingSkill`: grade evidence relevance/quality/recency (advisory)
- [x] `CitationGroundingSkill`: map claims to evidence references (advisory)
- [x] `StakeholderBriefingSkill`: audience-aware narrative from readout (advisory)
- [x] All skills have SKILL_ID + GOVERNANCE_LEVEL metadata
- [x] Tests: grading order, DOI quality boost, recency scoring, claim grounding, narrative generation

---

## Phase 5: Domain Cleanup & Governance (Low dependency, high polish) ✅ COMPLETE

### 5.1 Domain-Agnostic Core Boundary ✅ (2026-05-24)
**Change:** domain-agnostic-core-cleanup
**Depends on:** None (UI copy)
**Type:** REFACTOR
**Effort:** M
**Files:** `backend/services/feature_flags.py`, `backend/services/domain_neutral_labels.py`, `tests/test_feature_flags.py` (12 tests), `tests/test_domain_neutral_labels.py` (15 tests)

- [x] Feature flag `ENABLE_COMMERCE_ADAPTERS` (default: true) with env var override
- [x] `is_enabled()`, `commerce_adapters_enabled()`, `visible_store_types()`, `is_commerce_store_type()`
- [x] When disabled: Shopify/WooCommerce/Bsale store types hidden
- [x] Scientific domains default to neutral labels (DOI/ORCID, not SKU/barcode)
- [x] Tests: flag defaults, env overrides, commerce helpers, neutral labels
- [ ] Frontend nav integration (hide store types when disabled) *(deferred to frontend sprint)*

### 5.2 Legacy Commerce Adapter Containment *(deferred to frontend sprint)*
**Change:** domain-agnostic-core-cleanup
**Depends on:** 5.1
**Type:** REFACTOR (code organization)
**Effort:** M

- [ ] Move commerce logic to `backend/adapters/commerce/` package
- [ ] Feature flag integration in stores router
- [ ] SKU not auto-mapped for non-commerce domains
- [ ] Source profiling doesn't auto-suggest commerce mappings unless adapter active

### 5.3 UI Copy Domain Neutrality ✅ (2026-05-24)
**Change:** domain-agnostic-core-cleanup
**Depends on:** 5.1
**Type:** REFACTOR (i18n)
**Effort:** S
**Files:** `backend/services/domain_neutral_labels.py` (shared with 5.1), `tests/test_domain_neutral_labels.py`

- [x] Neutral EN/ES labels: canonical ID examples (DOI, ORCID, ROR, not SKU/barcode)
- [x] Secondary label examples (author, institution, venue, not brand)
- [x] Entity type examples (person, organization, publication, dataset, not product)
- [x] Destructive dialogs: "records/entities" not "products", neutral export filename
- [x] Commerce override: SKU/barcode labels only when `ENABLE_COMMERCE_ADAPTERS=true` AND domain="commerce"
- [x] Tests: neutral examples, commerce override, destructive dialog copy, all-metadata helper

### 5.4 Design Token Governance ✅ (2026-05-24)
**Change:** ukip-design-system-foundation
**Depends on:** None (CSS/design)
**Type:** REFACTOR
**Effort:** S
**Files:** `frontend/app/styles/design-tokens.md`

- [x] Documented semantic role rules: violet=brand, cyan=intelligence, emerald=evidence, amber=caution, red=risk
- [x] Enforced light mode as default (no OS dark auto-adopt)
- [x] Spacing guidance: comfortable hit areas, dashboard grid, dense table
- [x] Typography: tabular figures for metrics, large type only on narrative surfaces
- [x] Radius scale: sm (4px), md (8px), lg (12px), xl (16px), full (999px)

### 5.5 Evidence Provenance UI Semantics ✅ (2026-05-24)
**Change:** ukip-design-system-foundation
**Depends on:** 2.6
**Type:** NEW (component data contracts)
**Effort:** M
**Files:** `backend/services/provenance_ui_semantics.py`, `tests/test_provenance_ui_semantics.py` (14 tests)

- [x] `PROV_BADGES` dict: source (muted/upload), enrichment (cyan/sparkles), canonical (emerald/check-circle), authority (violet/shield-check)
- [x] `CONFIDENCE_LEVELS`: high (≥0.8, emerald), medium (≥0.5, warning), low (≥0.2, danger), unknown (<0.2, muted), review_required (warning)
- [x] Null-state config: de-emphasized style, 0.5 opacity, show reason
- [x] AI disclosure: AI-assisted (cpu icon, cyan) and AI-generated (bot icon, cyan) badges with tooltips
- [x] `get_prov_badge()`, `get_confidence_level()`, `get_ai_disclosure()` helpers
- [ ] React components (ProvBadge, ConfidenceIndicator) *(deferred to frontend sprint)*

### 5.6 Component Foundation Contract 🚧
**Change:** ukip-design-system-foundation
**Depends on:** 5.4
**Type:** REFACTOR (standardize existing)
**Effort:** M

- [x] Standardize Button/IconButton variants, sizes, states, accessibility
- [x] Standardize Input/Select/Textarea/Checkbox/Radio/Switch patterns
- [x] Establish semantic control/feedback tokens and a regression baseline
- [ ] Standardize Tabs, segmented controls, menus
- [ ] Standardize Panel/Surface/SectionHeader/EmptyState/ErrorBanner/Toast/Skeleton
- [ ] Standardize KPI/Metric/DeltaBadge/QualityBadge
- [ ] Standardize DataTable dense behavior
- [ ] Responsive stability: no overflow, touch targets, translated text

### 5.7 GenAI Cross-Cutting Governance ✅ (2026-05-24)
**Change:** ukip-enterprise-architecture-governance
**Depends on:** 3.1, 3.7
**Type:** REFACTOR (governance enforcement)
**Effort:** M
**Files:** `backend/services/genai_governance.py`, `tests/test_genai_governance.py` (18 tests)

- [x] `GenAIOutput` dataclass with output_type, confidence, evidence, provenance_source, requires_review
- [x] `validate_mapping_suggestion()`: confidence + evidence required, low-confidence → review_required
- [x] `validate_authority_candidate()`: always requires review, provenance required
- [x] `validate_narrative()`: evidence grounding required, provenance disclaimer
- [x] `validate_genai_output()` router dispatching to type-specific validators
- [x] `should_show_ai_badge()` always True; `get_governance_label()` → Review required / Auto-acceptable / AI-assisted
- [x] Tests: all 3 output types, governance violations, helpers, to_dict serialization
- [ ] Frontend: AI-assisted badge on suggestions *(deferred to frontend sprint)*

---

## Phase 6: Documentation & Operational Maturity ✅ COMPLETE

### 6.1 Architecture Decision Records ✅ (2026-05-24)
**Change:** ukip-enterprise-architecture-governance
**Type:** DOCUMENTATION
**Effort:** S
**Files:** `docs/adr/000-template.md`, `docs/adr/001-provenance-layering.md`, `docs/adr/002-canonical-governance.md`, `docs/adr/003-authority-resolution.md`, `docs/adr/004-enrichment-circuit-breaker.md`, `docs/adr/005-genai-mapping-governance.md`

- [x] Created `docs/adr/` directory with ADR template (000-template.md)
- [x] ADR-001: Entity Provenance Layering (4-layer model, layer boundaries, rollback safety)
- [x] ADR-002: Canonical Semantic Data Governance (profiling → mapping → linked-data pipeline)
- [x] ADR-003: Authority Resolution Pipeline (extraction → readiness → promotion with conflict detection)
- [x] ADR-004: Enrichment Circuit Breaker (CLOSED/OPEN/HALF_OPEN, per-provider, thread-safe)
- [x] ADR-005: GenAI Mapping Assistance Governance (type-specific validation, mandatory disclosure)
- [x] Template defines when ADRs are required (service boundaries, canonical rules, strategic deps)

### 6.2 Infrastructure Operations Architecture ✅ (2026-05-24)
**Change:** ukip-enterprise-architecture-governance
**Type:** DOCUMENTATION
**Effort:** M
**Files:** `docs/infrastructure-operations.md`

- [x] Deployment topology diagram (Next.js → FastAPI → SQLite/ChromaDB/DuckDB/External APIs)
- [x] Environment variable contract: 5 required (production), 10 optional, with purpose/secret/defaults
- [x] Startup guard documentation (required vars, insecure placeholder detection, CORS wildcard warning)
- [x] Health check documentation (`GET /health`, public, no auth)
- [x] Background worker documentation (enrichment worker, scheduler, scheduled imports/reports)
- [x] Operational metrics: API (request count, error rate, rate limits), enrichment (queue depth, circuit breaker), DB (file size, pool)
- [x] Backup/recovery documentation (SQLite file copy, ChromaDB directory, RAG rebuild)
- [x] Rollback safety documentation (provenance layering, harmonization undo, authority reject)

### 6.3 Application Service Architecture ✅ (2026-05-24)
**Change:** ukip-enterprise-architecture-governance
**Type:** DOCUMENTATION
**Effort:** S
**Files:** `docs/service-architecture.md`

- [x] 7 service boundaries documented: Ingestion, Enrichment, Reconciliation/Authority, Analytics/Intelligence, Reporting/Export, RAG/AI, Auth/Platform
- [x] Integration contracts table (producer → consumer → contract)
- [x] Service review checklist for future specs (layer boundaries, auth, validation, GenAI governance, ADR)

### 6.4 Business Stakeholder Scope ✅ (2026-05-24)
**Change:** ukip-enterprise-architecture-governance
**Type:** DOCUMENTATION
**Effort:** XS
**Files:** `docs/stakeholder-scope.md`

- [x] 5 stakeholder personas mapped to platform capabilities: Executive, Data Steward, Analyst, Innovation Transfer, Evaluator
- [x] Capability-to-outcome table for each persona
- [x] Audience preset summary linking to backend presets

---

## Effort Legend

| Size | Hours | Description |
|------|-------|-------------|
| XS | 2-4h | Config, i18n, helpers |
| S | 4-8h | Model, adapter, small service |
| M | 8-20h | Service + API + tests, or frontend feature |
| L | 20-40h | Full-stack feature (model + service + API + UI + tests) |

---

## Critical Path

```
Phase 1 (foundation) ──┬── Phase 2 (services) ──┬── Phase 3 (authority) ── Phase 4 (UX/exports)
                       │                         │
                       └── Phase 5 (cleanup) ────┘

Phase 6 (docs) can run in parallel at any time.
```

**Estimated total:** ~350-500 hours across all phases.
**Recommended parallel tracks:**
- Track A: Data/Authority (1.1→2.1→2.2→2.3→2.5→3.2→3.3→3.5→3.6→3.7→4.1)
- Track B: Provenance/UX (1.5→2.6→2.7→4.3→4.4→4.5→4.6)
- Track C: RAG Skills (1.6→2.8→2.9→4.2→4.8)
- Track D: Geography (1.2→2.4→3.4→4.7)
- Track E: Domain cleanup (5.1→5.2→5.3) + Design system (5.4→5.5→5.6)
