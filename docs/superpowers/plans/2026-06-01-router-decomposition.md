# Router Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split 5 oversized backend routers into 13 cohesive sub-modules, each under 600 LOC.

**Architecture:** Pure mechanical refactor — extract code into new files, update imports, register new routers in `main.py`. No behavioral changes. Existing 2480 tests are the safety net.

**Tech Stack:** FastAPI routers, SQLAlchemy, Pydantic models, pytest

**Spec:** `docs/superpowers/specs/2026-06-01-router-decomposition-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `backend/routers/workspace_reset_ops.py` | 25 helper functions + constants for workspace reset |
| Modify | `backend/routers/workspace_reset.py` | Trim to endpoints + Pydantic models, import from ops |
| Create | `backend/routers/ingest_helpers.py` | Parsing, dedup, materialization helpers + constants |
| Modify | `backend/routers/ingest.py` | Trim to 5 route handlers, import from helpers |
| Create | `backend/routers/analytics_analyzers.py` | Domain analyzer endpoints (topics, authors, geo) |
| Create | `backend/routers/analytics_ops.py` | Lookups, ops checks, concepts, epistemic, domain health |
| Modify | `backend/routers/analytics.py` | Trim to dashboard/discovery + shared state |
| Create | `backend/routers/authority_institutions.py` | Institution reconciliation endpoints + helpers |
| Create | `backend/routers/authority_records.py` | Record CRUD, thresholds, metrics, field lookup |
| Modify | `backend/routers/authority.py` | Trim to core resolution + shared constants |
| Create | `backend/routers/governance_sources.py` | Source profiling, mapping suggestions, readiness, JSON-LD |
| Create | `backend/routers/governance_field_correspondence.py` | Field correspondence rule CRUD |
| Create | `backend/routers/governance_field_correspondence_ops.py` | Field correspondence operations |
| Delete | `backend/routers/governance.py` | Replaced by 3 sub-routers |
| Modify | `backend/main.py` | Register new routers, remove old governance import |

---

## Refactor Pattern (applies to every task)

Each task follows the same mechanical pattern:

1. **Read the source file** to identify exact line ranges for extraction
2. **Create the new file(s)** with the extracted code + necessary imports
3. **Trim the original file** to remove extracted code, add imports from the new file if needed
4. **Update `backend/main.py`** to import and register new router(s)
5. **Update mock targets in tests** if any patch paths changed
6. **Run tests** to verify nothing broke
7. **Commit**

Since this is a pure refactor, the existing test suite IS the test. No new tests are needed.

---

### Task 1: Split `workspace_reset.py` (simplest, warm-up)

**Files:**
- Create: `backend/routers/workspace_reset_ops.py`
- Modify: `backend/routers/workspace_reset.py`

This is the simplest split: no mock target changes, no new router registration (the ops file has no endpoints). Good warm-up to validate the pattern.

- [ ] **Step 1: Read `workspace_reset.py` and identify extraction boundaries**

Read `backend/routers/workspace_reset.py`. Identify:
- Lines 1-49: imports, Pydantic models, router declaration
- Lines 52-615: all 25 helper functions + constants (`CONFIRMATION_TEXT`, `PRESERVED_RESOURCES`)
- Lines 618-893: the 2 endpoint handlers

- [ ] **Step 2: Create `workspace_reset_ops.py`**

Create `backend/routers/workspace_reset_ops.py` containing:
- All imports needed by the 25 helper functions
- Constants: `CONFIRMATION_TEXT`, `PRESERVED_RESOURCES`
- All 25 private helper functions (lines ~52-615): `_scope_details`, `_scoped_query`, `_ids`, `_existing_tables`, `_table_exists`, `_column_exists`, `_physical_columns`, `_safe_update`, `_scoped_where`, `_count_table`, `_ids_for_table`, `_count_annotation_rows`, `_delete_where_ids`, `_delete_scoped_table`, `_delete_scoped_model`, `_count_where_ids`, `_delete_annotations`, `_hard_delete_reset_rows`, `_delete_reset_dependencies_orm`, `_reset_workspace_counters_sql`, `_delete_link_dismissals`, `_audit_log_query`, `_delete_audit_logs`, `_member_user_ids`, `_preview_counts`

- [ ] **Step 3: Trim `workspace_reset.py`**

Remove the extracted helpers and constants from `workspace_reset.py`. Add:
```python
from backend.routers.workspace_reset_ops import (
    CONFIRMATION_TEXT, PRESERVED_RESOURCES,
    _preview_counts, _scope_details, _hard_delete_reset_rows,
    _delete_reset_dependencies_orm, _reset_workspace_counters_sql,
    _delete_annotations, _delete_link_dismissals, _delete_audit_logs,
    _member_user_ids, _delete_scoped_table, _delete_scoped_model,
    # ... all helpers used by the 2 endpoint handlers
)
```

Keep: imports, Pydantic models (`WorkspaceResetPreview`, `WorkspaceResetRequest`, `WorkspaceResetResponse`), `router = APIRouter(...)`, and the 2 endpoint handlers.

Pydantic models reference `PRESERVED_RESOURCES` — import it from `workspace_reset_ops`.

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python -m pytest backend/tests/ -x -q --tb=short 2>&1 | tail -20`
Expected: all tests pass, 0 failures

- [ ] **Step 5: Verify line counts**

Run: `wc -l backend/routers/workspace_reset.py backend/routers/workspace_reset_ops.py`
Expected: workspace_reset.py ~300, workspace_reset_ops.py ~600

- [ ] **Step 6: Commit**

```bash
git add backend/routers/workspace_reset.py backend/routers/workspace_reset_ops.py
git commit -m "refactor(workspace-reset): extract ops helpers into workspace_reset_ops.py"
```

---

### Task 2: Split `ingest.py`

**Files:**
- Create: `backend/routers/ingest_helpers.py`
- Modify: `backend/routers/ingest.py`
- Modify: `backend/tests/test_sprint74.py` (mock target update)
- Modify: `backend/tests/test_ingest_engine_routing.py` (mock target update)
- Modify: `backend/tests/test_dedup_entities.py` (mock target update)

- [ ] **Step 1: Read `ingest.py` and identify extraction boundaries**

Read `backend/routers/ingest.py`. Identify all helpers, constants, and the `SuggestMappingRequest` Pydantic model that move to `ingest_helpers.py`.

- [ ] **Step 2: Create `ingest_helpers.py`**

Create `backend/routers/ingest_helpers.py` containing:
- All imports needed by the helpers
- Pydantic model: `SuggestMappingRequest`
- Constants: `_MAX_UPLOAD_BYTES`, `_MAX_ROWS`, `_CHUNK_SIZE`, `MAPPABLE_MODEL_FIELDS`, `_VIRTUAL_MODEL_FIELDS`, `_SCIENCE_AUTO_MAPPING`, `_FIELD_DESCRIPTIONS`, `_VALID_UKIP_FIELDS`, `_SUGGEST_SYSTEM_PROMPT`
- All helper functions: `_dedup_before_insert`, `_parse_llm_mapping`, `_parse_file_to_records`, `_parse_science_import`, `_try_parse_science_import`, `_parse_science_records`, `_record_virtual_field`, `_infer_entity_type_hint`, `_create_import_batch`, `_materialize_graph`, `_shadow_engine_call`

- [ ] **Step 3: Trim `ingest.py`**

Remove extracted code from `ingest.py`. Add imports from `ingest_helpers`. Keep: router, 5 endpoint handlers, their direct imports.

- [ ] **Step 4: Update mock targets AND direct imports in test files**

Search for ALL references to moved symbols — both `patch()` string targets AND direct `from ... import` statements:

```bash
grep -rn "backend.routers.ingest\.\(_\|MAPPABLE\)\|from backend.routers.ingest import _\|from backend.routers.ingest import MAPPABLE" backend/tests/
```

There are TWO kinds of references to update:

**A) `patch()` string targets** (in `@patch("backend.routers.ingest._foo")` or `with patch(...)`):
- `backend.routers.ingest._parse_llm_mapping` → `backend.routers.ingest_helpers._parse_llm_mapping`
- `backend.routers.ingest._VALID_UKIP_FIELDS` → `backend.routers.ingest_helpers._VALID_UKIP_FIELDS`
- `backend.routers.ingest._dedup_before_insert` → `backend.routers.ingest_helpers._dedup_before_insert`
- `backend.routers.ingest._materialize_graph` → `backend.routers.ingest_helpers._materialize_graph`

**B) Direct `from ... import` statements** (these will cause ImportError if not updated):
- `test_sprint74.py`: `from backend.routers.ingest import _parse_llm_mapping, _VALID_UKIP_FIELDS` → `from backend.routers.ingest_helpers import _parse_llm_mapping, _VALID_UKIP_FIELDS`
- `test_ingest_engine_routing.py`: `from backend.routers.ingest import _materialize_graph` → `from backend.routers.ingest_helpers import _materialize_graph`
- `test_dedup_entities.py`: `from backend.routers.ingest import _dedup_before_insert` → `from backend.routers.ingest_helpers import _dedup_before_insert`

Patch targets that reference top-level imports in `ingest.py` (like `materialize_scientific_import_graph`, `engine_bridge.entity_to_publication`) stay unchanged.

- [ ] **Step 5: Run tests**

Run: `.venv/Scripts/python -m pytest backend/tests/ -x -q --tb=short 2>&1 | tail -20`
Expected: all tests pass

- [ ] **Step 6: Verify line counts**

Run: `wc -l backend/routers/ingest.py backend/routers/ingest_helpers.py`
Expected: ingest.py ~500, ingest_helpers.py ~550

- [ ] **Step 7: Commit**

```bash
git add backend/routers/ingest.py backend/routers/ingest_helpers.py backend/tests/test_sprint74.py backend/tests/test_ingest_engine_routing.py backend/tests/test_dedup_entities.py
git commit -m "refactor(ingest): extract helpers into ingest_helpers.py"
```

---

### Task 3: Split `analytics.py`

**Files:**
- Create: `backend/routers/analytics_analyzers.py`
- Create: `backend/routers/analytics_ops.py`
- Modify: `backend/routers/analytics.py`
- Modify: `backend/main.py` (add 2 new router registrations)

**Critical constraint:** Shared state (`_SimpleCache`, `_analytics_cache`, `_dashboard_cache`, `invalidate_analytics_for_domain`, `_legacy_coauthorship_network`) MUST stay in `analytics.py` because external modules import from `backend.routers.analytics`.

**Shared helpers:** `_validate_domain_id` is used by both `analytics.py` dashboard endpoints and `analytics_analyzers.py` analyzer endpoints. It MUST stay in `analytics.py` (where shared state lives) and be imported by `analytics_analyzers.py`:
```python
# In analytics_analyzers.py
from backend.routers.analytics import _validate_domain_id
```
Same applies to `_parse_attrs`, `_nested_value`, `_text_value` if they are called from `analytics.py` endpoints. During Step 1, grep for all call sites of each helper to determine correct placement. If a helper is only used by analyzer endpoints, it stays in `analytics_analyzers.py`. If used by both files, it goes in `analytics.py` and is imported.

- [ ] **Step 1: Read `analytics.py` and map the 3-way split**

Read `backend/routers/analytics.py`. Identify exact line ranges for:
- Shared state + dashboard/discovery endpoints → stays in `analytics.py`
- Domain analyzer endpoints → `analytics_analyzers.py`
- Lookups, ops, concepts, epistemic, domain health → `analytics_ops.py`

**Important:** For each helper function (`_validate_domain_id`, `_parse_attrs`, `_nested_value`, `_text_value`), grep for ALL call sites in `analytics.py` to determine if they are used by endpoints staying in `analytics.py` or only by endpoints moving to `analytics_analyzers.py`. Place the helper in the file that uses it; if both files use it, keep it in `analytics.py` and import from there.

- [ ] **Step 2: Create `analytics_analyzers.py`**

Create `backend/routers/analytics_analyzers.py` with:
- `router = APIRouter(tags=["analytics"])`
- Import shared helpers from `analytics.py` if needed (e.g., `from backend.routers.analytics import _validate_domain_id`)
- Endpoints: `/analyzers/topics/{domain_id}`, `/analyzers/cooccurrence/{domain_id}`, `/analyzers/clusters/{domain_id}`, `/analyzers/correlation/{domain_id}`, `/analyzers/trends/{domain_id}`, `/analyzers/authors/{domain_id}/{record_id}`, `/analyzers/authors/{domain_id}`, `/analyzers/geographic/{domain_id}`, `/analyzers/geographic/{domain_id}/country/{country_code}`

- [ ] **Step 3: Create `analytics_ops.py`**

Create `backend/routers/analytics_ops.py` with:
- `router = APIRouter(tags=["analytics"])`
- Helpers: `_get_secondary_label_counts`, `_require_epistemology`, `_require_discourse_community`
- Endpoints: `/stats`, `/secondary-labels`, `/brands`, `/product-types`, `/classifications`, `/health`, `/ops/checks`, `/ops/checks/run`, `/ops/enterprise-readiness`, `/ops/tenant-model`, `/analytics/concepts/{domain_id}/materialize`, `/analytics/concepts/{domain_id}/tree`, `/analytics/concepts/{domain_id}/{concept_node_id}`, `/analytics/epistemic/classify-batch`, `/analytics/epistemic/distribution`, `/analytics/domain-health/compare`, `/analytics/domain-health`

- [ ] **Step 4: Trim `analytics.py`**

Remove extracted endpoints and their private helpers from `analytics.py`. Keep: shared state, dashboard/discovery endpoints, keyword signals, researchers, coverage, ROI, benchmarks, cache invalidation.

- [ ] **Step 5: Update `main.py`**

Add imports and router registrations. Insert AFTER the existing `analytics.router` line:

```python
from backend.routers import analytics_analyzers, analytics_ops
# ... in the registration block:
app.include_router(analytics_analyzers.router)
app.include_router(analytics_ops.router)
```

- [ ] **Step 6: Verify external imports are unbroken**

Run:
```bash
grep -rn "from backend.routers.analytics import" backend/ --include="*.py" | grep -v __pycache__
```

Confirm that `invalidate_analytics_for_domain`, `_legacy_coauthorship_network`, `_dashboard_cache`, `_analytics_cache`, `_SimpleCache` all still resolve to `backend.routers.analytics`.

- [ ] **Step 7: Run tests**

Run: `.venv/Scripts/python -m pytest backend/tests/ -x -q --tb=short 2>&1 | tail -20`
Expected: all tests pass

- [ ] **Step 8: Verify line counts**

Run: `wc -l backend/routers/analytics.py backend/routers/analytics_analyzers.py backend/routers/analytics_ops.py`
Expected: analytics.py ~500, analytics_analyzers.py ~450, analytics_ops.py ~450

- [ ] **Step 9: Commit**

```bash
git add backend/routers/analytics.py backend/routers/analytics_analyzers.py backend/routers/analytics_ops.py backend/main.py
git commit -m "refactor(analytics): split into analyzers + ops sub-routers"
```

---

### Task 4: Split `authority.py`

**Files:**
- Create: `backend/routers/authority_institutions.py`
- Create: `backend/routers/authority_records.py`
- Modify: `backend/routers/authority.py`
- Modify: `backend/main.py` (add 2 new router registrations)
- Modify: test files that patch `RORAdapter.lookup` (mock target change)

**Critical constraint:** `_authority_resolve_all` stays in `authority.py` — it is the primary test patch target (13+ test files).

**Route ordering:** `authority_records.router` MUST be registered AFTER `authority.router` and `authority_institutions.router` because it contains the catch-all `GET /authority/{field}`.

- [ ] **Step 1: Read `authority.py` and map the 3-way split**

Read `backend/routers/authority.py`. Identify exact line ranges for:
- Institution reconciliation helpers + endpoints → `authority_institutions.py`
- Record management + thresholds + metrics + field lookup → `authority_records.py`
- Core resolution + shared constants → stays in `authority.py`

- [ ] **Step 2: Create `authority_institutions.py`**

Create `backend/routers/authority_institutions.py` with:
- `router = APIRouter(tags=["authority"])`
- Pydantic models: `InstitutionReconcilePreviewRequest`, `InstitutionReconcileApplyRequest`
- Helpers: `_institution_candidate_rows`, `_preview_institution_reconciliation`, `_find_existing_institution_record`, `_persist_institution_match`, `_candidate_identity`, `_author_names_for_institution`, `_find_author_authority_record`, `_ensure_author_institution_links`
- Endpoints: institution reconcile preview, apply, review queue, accept, reject

- [ ] **Step 3: Create `authority_records.py`**

Create `backend/routers/authority_records.py` with:
- `router = APIRouter(tags=["authority"])`
- Endpoints: link confirm/reject, bulk confirm/reject, list records, confirm/reject/delete record, threshold CRUD, metrics, `GET /authority/{field}` (catch-all — MUST be last route in file)

- [ ] **Step 4: Trim `authority.py`**

Remove extracted code. Keep: shared constants (`_FIELD_RE`, `_AFFILIATION_LINK_TYPE`), core resolution helpers, `_authority_resolve_all`, and core resolution endpoints (resolve, resolve author profile, resolve batch, job status, queue summary, author review queue, author metrics, author compare, author affiliations).

- [ ] **Step 5: Update `main.py`**

Add imports. Registration order matters — insert `authority_records` AFTER the other two:

```python
from backend.routers import authority_institutions, authority_records
# ... in the registration block:
app.include_router(authority.router)          # existing line
app.include_router(authority_institutions.router)  # NEW — after authority
app.include_router(authority_records.router)        # NEW — LAST (catch-all route)
```

- [ ] **Step 6: Update mock targets in test files**

Search and update:
```bash
grep -rn "backend.routers.authority.RORAdapter" backend/tests/
```

Change `backend.routers.authority.RORAdapter` → `backend.routers.authority_institutions.RORAdapter` in affected test files.

Confirm `backend.routers.authority._authority_resolve_all` is unchanged (should still work).

- [ ] **Step 7: Run tests**

Run: `.venv/Scripts/python -m pytest backend/tests/ -x -q --tb=short 2>&1 | tail -20`
Expected: all tests pass

- [ ] **Step 8: Verify line counts**

Run: `wc -l backend/routers/authority.py backend/routers/authority_institutions.py backend/routers/authority_records.py`
Expected: authority.py ~550, authority_institutions.py ~350, authority_records.py ~450

- [ ] **Step 9: Commit**

```bash
git add backend/routers/authority.py backend/routers/authority_institutions.py backend/routers/authority_records.py backend/main.py backend/tests/
git commit -m "refactor(authority): split into institutions + records sub-routers"
```

---

### Task 5: Split `governance.py` (delete original)

**Files:**
- Create: `backend/routers/governance_sources.py`
- Create: `backend/routers/governance_field_correspondence.py`
- Create: `backend/routers/governance_field_correspondence_ops.py`
- Delete: `backend/routers/governance.py`
- Modify: `backend/main.py` (replace 1 registration with 3)

This is the only task that deletes the original file entirely.

- [ ] **Step 1: Read `governance.py` and map the 3-way split**

Read `backend/routers/governance.py`. Identify exact line ranges for:
- Source profiling + mapping suggestions + readiness + JSON-LD → `governance_sources.py`
- Field correspondence rule CRUD + serialization helpers → `governance_field_correspondence.py`
- Field correspondence operations (metrics, seed, apply, rollback, etc.) → `governance_field_correspondence_ops.py`

Note: `governance_field_correspondence_ops.py` may need to import serialization helpers from `governance_field_correspondence.py` (e.g., `_serialize_rule`, `_serialize_field_correspondence_job`). Identify these cross-dependencies.

- [ ] **Step 2: Create `governance_sources.py`**

Create `backend/routers/governance_sources.py` with:
- `router = APIRouter(tags=["governance"])`
- Pydantic models: `ProfileRequest`, `MappingSuggestionResponse`, `RejectPayload`, `BulkSuggestionReviewPayload`, `BulkSuggestionReviewResponse`, `FamilyCountsResponse`, `ReadinessResponse`
- Helper: `_get_mapping_service`
- Endpoints: create/get source profile, get candidates, list/bulk-review/accept/reject mapping suggestions, authority readiness, JSON-LD export

- [ ] **Step 3: Create `governance_field_correspondence.py`**

Create `backend/routers/governance_field_correspondence.py` with:
- `router = APIRouter(tags=["governance"])`
- Pydantic models: `FieldCorrespondenceRuleResponse`, `FieldCorrespondenceRulePayload`, `FieldCorrespondenceEvidenceScore`, `FieldCorrespondenceAuditEntry`
- Helpers: `_json_list`, `_json_object`, `_serialize_rule`, `_dump_rule`, `_audit_rule_change`, `_evidence_level`, `_validate_identifier_value`, `_collision_count_for_rule`
- Endpoints: list rules, create rule, update rule, deactivate, reactivate, evidence score, audit list

- [ ] **Step 4: Create `governance_field_correspondence_ops.py`**

Create `backend/routers/governance_field_correspondence_ops.py` with:
- `router = APIRouter(tags=["governance"])`
- Pydantic models: `PreventiveRuleSeedResponse`, `FieldCorrespondenceImpactExample`, `FieldCorrespondenceImpactResponse`, `AmbiguousSourceMetric`, `GovernanceMetricsResponse`, `FieldCorrespondenceApplyPayload`, `FieldCorrespondenceReviewPayload`, `FieldCorrespondenceApplyResponse`, `FieldCorrespondenceJobResponse`, `FieldCorrespondenceRollbackResponse`
- Helpers: `_preventive_rule_candidates`, `_field_correspondence_matches`, `_rule_candidate_query`, `_extract_rule_value`, `_serialize_field_correspondence_job`
- Endpoints: governance metrics, seed preventive, list jobs, review CSV, rollback, impact preview, apply rule, set review status
- Import shared helpers from `governance_field_correspondence` if needed (e.g., `_serialize_rule`)

- [ ] **Step 5: Verify no external imports from `backend.routers.governance`**

```bash
grep -rn "from backend.routers.governance import\|from backend.routers import governance\|backend.routers.governance\." backend/ --include="*.py" | grep -v __pycache__ | grep -v governance_
```

If any external consumers exist, they must be updated to import from the new module. If only `main.py` imports it, proceed with deletion.

- [ ] **Step 6: Delete `governance.py` and update `main.py`**

```bash
git rm backend/routers/governance.py
```

In `main.py`, replace:
```python
governance,
```
with:
```python
governance_sources,
governance_field_correspondence,
governance_field_correspondence_ops,
```

And replace:
```python
app.include_router(governance.router)
```
with:
```python
app.include_router(governance_sources.router)
app.include_router(governance_field_correspondence.router)
app.include_router(governance_field_correspondence_ops.router)
```

- [ ] **Step 7: Update mock targets in test files**

```bash
grep -rn "backend.routers.governance" backend/tests/ | grep -v __pycache__
```

Update any patch targets from `backend.routers.governance.*` to the appropriate new module.

- [ ] **Step 8: Run tests**

Run: `.venv/Scripts/python -m pytest backend/tests/ -x -q --tb=short 2>&1 | tail -20`
Expected: all tests pass

- [ ] **Step 9: Verify line counts**

Run: `wc -l backend/routers/governance_sources.py backend/routers/governance_field_correspondence.py backend/routers/governance_field_correspondence_ops.py`
Expected: ~400, ~500, ~400

- [ ] **Step 10: Commit**

```bash
git add backend/routers/governance_sources.py backend/routers/governance_field_correspondence.py backend/routers/governance_field_correspondence_ops.py backend/main.py backend/tests/
git rm backend/routers/governance.py
git commit -m "refactor(governance): split into sources + field-correspondence sub-routers"
```

---

### Task 6: Housekeeping

**Files:**
- Modify: `.gitignore`
- Stage: `docs/superpowers/PR-coauthor-v2.md`

- [ ] **Step 1: Add `.playwright-mcp/` to `.gitignore`**

Append to `.gitignore`:
```
# Browser automation artifacts (Playwright MCP)
.playwright-mcp/
```

- [ ] **Step 2: Commit untracked PR doc**

```bash
git add .gitignore docs/superpowers/PR-coauthor-v2.md
git commit -m "chore: gitignore playwright-mcp, commit coauthor-v2 PR doc"
```

- [ ] **Step 3: Update memory file**

Update `disambig-authority-optimization.md` in the memory directory to reflect all 12 tasks are complete. Remove the "T8-12 pending" note from `MEMORY.md`.

---

### Task 7: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `.venv/Scripts/python -m pytest backend/tests/ -q --tb=short 2>&1 | tail -20`
Expected: 2480 tests pass, 0 failures

- [ ] **Step 2: Verify all routers are under 800 LOC**

Run: `wc -l backend/routers/*.py | sort -rn | head -20`
Expected: no file exceeds 800 LOC (the previous top-5 offenders are now split)

- [ ] **Step 3: Verify the app starts**

Run: `cd /d/universal-knowledge-intelligence-platform && UKIP_SKIP_STARTUP_SIDE_EFFECTS=1 .venv/Scripts/python -c "from backend.main import app; print('OK:', len(app.routes), 'routes')"`
Expected: prints "OK: <N> routes" without import errors

- [ ] **Step 4: Commit summary (if any fixups needed)**

If any fixups were made during verification, commit them:
```bash
git add -A
git commit -m "fix: post-refactor fixups from final verification"
```
