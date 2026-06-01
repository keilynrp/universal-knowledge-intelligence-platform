# Router Decomposition Design

**Date:** 2026-06-01
**Status:** Approved
**Goal:** Split 5 backend routers that exceed the 800 LOC ceiling into cohesive sub-modules targeting 300-500 LOC each.

## Principles

- Domain-based splits: each new file owns a coherent sub-domain of endpoints.
- Helpers follow their consumers: private functions move with the routes that call them.
- Pydantic models stay co-located with the router that uses them (no separate schemas/ directory).
- Imports between sibling routers are allowed for shared constants; heavy shared logic goes into a `_common` helper if needed.
- All new routers are registered via `include_router` in `backend/main.py` with the same tags/prefixes as the originals. Each new file gets its own `router = APIRouter(tags=[...])` and `main.py` adds one `include_router` per file.
- Route registration order matters: `authority_records.router` (which contains the catch-all `GET /authority/{field}`) must be registered AFTER `authority.router` and `authority_institutions.router` to avoid path-parameter shadowing.
- Tests must pass unchanged after the refactor. Mock targets that change module paths must be updated (see migration tables per section).

---

## 1. `authority.py` (1707 LOC -> 3 files)

### `authority.py` (~550 LOC) — Core Resolution
- Helpers: `_persist_authority_candidates`, `_make_nil_authority_record`, `_link_confidence`, `_resolve_author_affiliation`, `_authority_resolve_all` (patch target for tests — stays here)
- Endpoints: resolve single, resolve author profile, resolve batch, job status, queue summary, author review queue, author metrics, author compare, author affiliations
- Shared constants: `_FIELD_RE`, `_AFFILIATION_LINK_TYPE`, logger

### `authority_institutions.py` (~350 LOC) — Institution Reconciliation
- Pydantic models: `InstitutionReconcilePreviewRequest`, `InstitutionReconcileApplyRequest`
- Helpers: `_institution_candidate_rows`, `_preview_institution_reconciliation`, `_find_existing_institution_record`, `_persist_institution_match`, `_candidate_identity`, `_author_names_for_institution`, `_find_author_authority_record`, `_ensure_author_institution_links`
- Endpoints: institution reconcile preview, institution reconcile apply, institution review queue, institution accept, institution reject

### `authority_records.py` (~450 LOC) — Record Management & Thresholds
- Endpoints: list records, confirm record, reject record, delete record, bulk confirm, bulk reject, link confirm, link reject
- Threshold CRUD: upsert, list, delete
- Metrics endpoint, field lookup (`GET /authority/{field}`)

**Mock target migration:**

| Old path | New path |
|----------|----------|
| `backend.routers.authority._authority_resolve_all` | unchanged (stays in `authority.py`) |
| `backend.routers.authority.RORAdapter.lookup` | `backend.routers.authority_institutions.RORAdapter.lookup` |

---

## 2. `governance.py` (1525 LOC -> 3 files)

### `governance_sources.py` (~400 LOC) — Source Profiling, Mapping Suggestions, Readiness & Export
- Pydantic models: `ProfileRequest`, `MappingSuggestionResponse`, `RejectPayload`, `BulkSuggestionReviewPayload`, `BulkSuggestionReviewResponse`, `FamilyCountsResponse`, `ReadinessResponse`
- Helper: `_get_mapping_service`
- Endpoints: create source profile, get source profile, get source candidates, list mapping suggestions, bulk review, accept suggestion, reject suggestion, authority readiness, JSON-LD export

Rationale: readiness + JSON-LD are thematically adjacent to source profiling (both assess data source quality). Merging avoids a ~100 LOC orphan file.

### (deleted) `governance.py` — No longer needed as a standalone router. The `governance` tag is shared across the 3 sub-routers.
- Pydantic models: `ProfileRequest`, `MappingSuggestionResponse`, `RejectPayload`, `BulkSuggestionReviewPayload`, `BulkSuggestionReviewResponse`
- Helper: `_get_mapping_service`
- Endpoints: create source profile, get source profile, get source candidates, list mapping suggestions, bulk review, accept suggestion, reject suggestion

### `governance_field_correspondence.py` (~500 LOC) — Field Correspondence Rules
- Pydantic models: `FieldCorrespondenceRuleResponse`, `FieldCorrespondenceRulePayload`, `FieldCorrespondenceEvidenceScore`, `FieldCorrespondenceAuditEntry`
- Helpers: `_json_list`, `_json_object`, `_serialize_rule`, `_dump_rule`, `_audit_rule_change`, `_evidence_level`, `_validate_identifier_value`, `_collision_count_for_rule`
- Endpoints: list rules, create rule, update rule, deactivate, reactivate, evidence score, audit list

### `governance_field_correspondence_ops.py` (~400 LOC) — Field Correspondence Operations
- Pydantic models: `PreventiveRuleSeedResponse`, `FieldCorrespondenceImpactExample`, `FieldCorrespondenceImpactResponse`, `AmbiguousSourceMetric`, `GovernanceMetricsResponse`, `FieldCorrespondenceApplyPayload`, `FieldCorrespondenceReviewPayload`, `FieldCorrespondenceApplyResponse`, `FieldCorrespondenceJobResponse`, `FieldCorrespondenceRollbackResponse`
- Helpers: `_preventive_rule_candidates`, `_field_correspondence_matches`, `_rule_candidate_query`, `_extract_rule_value`, `_serialize_field_correspondence_job`
- Endpoints: governance metrics, seed preventive, list jobs, review CSV export, rollback job, impact preview, apply rule, set review status

---

## 3. `analytics.py` (1409 LOC -> 3 files)

### `analytics.py` (~500 LOC) — Dashboard, Discovery & Shared State
- **Shared state (consumed by sibling routers and external modules):** `_SimpleCache`, `_analytics_cache`, `_dashboard_cache`, `invalidate_analytics_for_domain`, `_legacy_coauthorship_network`. These MUST stay in this file because external modules import them from `backend.routers.analytics`.
- Helpers: `_abstract_matches`, `_dashboard_external_attention`, `_resolve_benchmark_org`
- Endpoints: keyword signals (materialize, get), researchers by topic, topic-researcher graph, abstract coverage, ROI simulation, dashboard summary, discover patterns, dashboard compare, benchmarks (list profiles, evaluate), cache invalidation

**External consumers of shared state (do NOT change these import paths):**

| Symbol | Imported by |
|--------|-------------|
| `invalidate_analytics_for_domain` | `backend.enrichment_worker` |
| `_legacy_coauthorship_network` | `backend.routers.coauthorship` |
| `_dashboard_cache` | `backend.services.derived_status_service` |
| `_analytics_cache` | `backend.routers.admin_data_fixes` |
| `_SimpleCache`, `_analytics_cache`, `_dashboard_cache`, `invalidate_analytics_for_domain` | `backend.tests.test_sprint83` |

### `analytics_analyzers.py` (~450 LOC) — Domain Analyzers
- Helpers: `_validate_domain_id`, `_parse_attrs`, `_nested_value`, `_text_value`
- Endpoints: topics, cooccurrence, clusters, correlation, trends, authors, author detail, geographic, geographic country

### `analytics_ops.py` (~450 LOC) — Lookups, Ops & Specialized Analytics
- Helpers: `_get_secondary_label_counts`, `_require_epistemology`, `_require_discourse_community`
- Endpoints: stats, secondary labels, brands, product-types, classifications, health check, ops checks (list, run), enterprise readiness, tenant model, concepts (materialize, tree, detail), epistemic (classify batch, distribution), domain health (compare, health)

---

## 4. `ingest.py` (1053 LOC -> 2 files)

### `ingest.py` (~500 LOC) — Route Handlers
- 5 endpoints: suggest-mapping, preview, upload, analyze, export
- Imports helpers and constants from `ingest_helpers`

### `ingest_helpers.py` (~550 LOC) — Parsing, Dedup & Materialization
- Pydantic model: `SuggestMappingRequest`
- Constants: `_MAX_UPLOAD_BYTES`, `_MAX_ROWS`, `_CHUNK_SIZE`, `MAPPABLE_MODEL_FIELDS`, `_VIRTUAL_MODEL_FIELDS`, `_SCIENCE_AUTO_MAPPING`, `_FIELD_DESCRIPTIONS`, `_VALID_UKIP_FIELDS`, `_SUGGEST_SYSTEM_PROMPT`
- Helpers: `_dedup_before_insert`, `_parse_llm_mapping`, `_parse_file_to_records`, `_parse_science_import`, `_try_parse_science_import`, `_parse_science_records`, `_record_virtual_field`, `_infer_entity_type_hint`, `_create_import_batch`, `_materialize_graph`, `_shadow_engine_call`

**Mock target migration:**

| Old path | New path |
|----------|----------|
| `backend.routers.ingest._parse_llm_mapping` | `backend.routers.ingest_helpers._parse_llm_mapping` |
| `backend.routers.ingest._VALID_UKIP_FIELDS` | `backend.routers.ingest_helpers._VALID_UKIP_FIELDS` |
| `backend.routers.ingest._dedup_before_insert` | `backend.routers.ingest_helpers._dedup_before_insert` |
| `backend.routers.ingest._materialize_graph` | `backend.routers.ingest_helpers._materialize_graph` |
| `backend.routers.ingest.materialize_scientific_import_graph` | unchanged (top-level import in `ingest.py`) |
| `backend.routers.ingest.engine_bridge.entity_to_publication` | unchanged (top-level import in `ingest.py`) |

**Affected test files:** `test_sprint74.py`, `test_ingest_engine_routing.py`, `test_dedup_entities.py`

---

## 5. `workspace_reset.py` (893 LOC -> 2 files)

### `workspace_reset.py` (~300 LOC) — Endpoints
- Pydantic models: `WorkspaceResetPreview`, `WorkspaceResetRequest`, `WorkspaceResetResponse`
- Endpoints: preview, reset
- Imports ops from `workspace_reset_ops`

### `workspace_reset_ops.py` (~600 LOC) — Internal Operations
- Constants: `CONFIRMATION_TEXT`, `PRESERVED_RESOURCES`
- Helpers (25): scope detection, schema introspection, query filtering, counting/ID retrieval, deletion strategies, cascading reset, audit log operations, preview counts

**Dependency direction:** `workspace_reset.py` imports from `workspace_reset_ops.py`, never the reverse. Pydantic models that reference `PRESERVED_RESOURCES` import the constant from `workspace_reset_ops`.

---

## 6. Housekeeping (tracked separately from router refactor)

### Untracked files
- `.playwright-mcp/` — Add to `.gitignore`
- `docs/superpowers/PR-coauthor-v2.md` — Commit as project documentation

### Memory update
- Update `disambig-authority-optimization.md` to reflect all 12 tasks complete

---

## Test Impact

- **No behavioral changes** — all endpoints retain identical paths, auth, and response shapes.
- **Mock targets** — see migration tables in sections 1 and 4. The `analytics.py` shared state symbols keep their original import paths.
- Full test suite (2480 tests) must pass green after refactor.

## File Count Summary

| Original | New files | Total LOC (unchanged) |
|----------|-----------|----------------------|
| `authority.py` | 3 | 1707 |
| `governance.py` | 3 | 1525 |
| `analytics.py` | 3 | 1409 |
| `ingest.py` | 2 | 1053 |
| `workspace_reset.py` | 2 | 893 |
| **Total** | **13 files** | **6587** |
