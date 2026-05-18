## 1. Shared Delegation Infrastructure

- [x] 1.1 Create `backend/services/engine_delegation.py` with `_get_engine_client(request)` helper that extracts the EngineClient from `request.app.state`
- [x] 1.2 Add `ENGINE_DELEGATION_THRESHOLD` env var support (default: 100) for size-based delegation decisions
- [x] 1.3 Add shared logging pattern: `logger.warning("Engine %s delegation failed, falling back to Python: %s", pipeline, exc)`

## 2. Analytics Delegation

- [x] 2.1 Implement `try_engine_analytics(client, domain_id, mode, top_n, org_id)` in `engine_delegation.py` — calls `process_analytics()`, converts proto `AnalyticsResponse` to Python dict format, returns `None` on failure
- [x] 2.2 Implement response converters: `_convert_topics(response)`, `_convert_cooccurrence(response)`, `_convert_clusters(response)`, `_convert_correlation(response)` matching existing API contract
- [x] 2.3 Wire `/analyzers/topics/{domain_id}` to try engine delegation before Python fallback (after cache check, before `_topic_analyzer.top_topics`)
- [x] 2.4 Wire `/analyzers/cooccurrence/{domain_id}` to try engine delegation before Python fallback
- [x] 2.5 Wire `/analyzers/clusters/{domain_id}` to try engine delegation before Python fallback
- [x] 2.6 Wire `/analyzers/correlation/{domain_id}` to try engine delegation before Python fallback
- [x] 2.7 Write tests: mock engine returns valid analytics response → verify converted format matches Python output shape
- [x] 2.8 Write tests: engine unavailable → verify Python fallback produces result
- [x] 2.9 Write tests: cached result → verify no gRPC call made

## 3. Disambiguation Delegation

- [x] 3.1 Implement `try_engine_disambiguation(client, field_name, values, threshold, similarity_threshold)` in `engine_delegation.py` — calls `process_disambiguation()`, converts proto `DisambiguationResponse` clusters to `{"canonical": str, "variations": [str], "count": int}` groups
- [x] 3.2 Wire `/disambiguate/{field}` to count unique values, delegate to engine if count > threshold and engine available, else use Python `_build_disambig_groups`
- [x] 3.3 Write tests: large dataset (>100 values) + mock engine → verify delegation and format conversion
- [x] 3.4 Write tests: small dataset (<100 values) → verify Python path used without engine attempt
- [x] 3.5 Write tests: engine unavailable for large dataset → verify Python fallback

## 4. Normalization Delegation

- [x] 4.1 Implement `try_engine_normalization(client, field_name, values, mode, rules)` in `engine_delegation.py` — calls `process_normalization()`, returns `{original: normalized}` mapping or `None`
- [x] 4.2 Wire `/rules/apply` to batch exact-match rules via engine when value count > threshold, keep regex rules in Python
- [x] 4.3 Write tests: bulk exact-match rules + mock engine → verify delegation returns mapping
- [x] 4.4 Write tests: regex rules → verify Python path always used
- [x] 4.5 Write tests: engine unavailable → verify Python row-by-row fallback

## 5. Connector Delegation

- [x] 5.1 Implement `try_engine_connectors(client, source, query_type, queries, limit)` in `engine_delegation.py` — calls `process_connectors()`, converts proto `Publication` to Python dict, returns `None` on failure
- [x] 5.2 Wire scientific import paths to support engine delegation when opt-in flag is set (e.g., `use_engine=True` parameter)
- [x] 5.3 Ensure Python-side rate limiter is bypassed when delegating to engine (engine has its own)
- [x] 5.4 Write tests: mock engine returns publications → verify conversion to Python dict format
- [x] 5.5 Write tests: engine unavailable → verify Python adapter fallback
- [x] 5.6 Write tests: delegation disabled → verify Python adapter used directly

## 6. Integration and Verification

- [x] 6.1 Run full Python test suite to verify no regressions in existing endpoints
- [x] 6.2 Add E2E test (behind `UKIP_ENGINE_E2E=1` flag): analytics delegation to running engine, verify response format
- [x] 6.3 Add E2E test: disambiguation delegation with 500+ values, verify engine speedup
- [x] 6.4 Update `backend/routers/engine.py` health endpoint to report delegation status per pipeline
- [x] 6.5 Document `ENGINE_DELEGATION_THRESHOLD` env var in deployment docs
