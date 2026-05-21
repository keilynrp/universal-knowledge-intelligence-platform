# UKIP Codemaps Index

**Last Updated:** 2026-05-20 (enrichment-scheduler feature)

Navigation guide to architectural documentation for the Universal Knowledge Intelligence Platform.

## Overview

UKIP is a domain-agnostic entity intelligence platform combining semantic enrichment, authority resolution, graph materialization, and knowledge synthesis. The architecture emphasizes separation of concerns, single-source-of-truth data contracts, and safe isolation patterns.

## Core Areas

### [Backend Architecture](backend.md)
Main services, routers, and data processing pipeline. Entry point: `backend/main.py` (slim 160-line orchestrator).

Key subsystems:
- **Authentication & Authorization** — RBAC with 4 roles (super_admin, admin, editor, viewer)
- **Entity Management** — Ingestion, enrichment, harmonization, authority resolution
- **Enrichment Scheduling** — Per-domain staleness detection and re-queuing (NEW)
- **Analytics & Reporting** — Dashboards, OLAP cubes, topic modeling, correlation analysis
- **Knowledge Synthesis** — RAG, semantic indexing, vector store integration

### [Data Schemas & Contracts](schemas.md)
Type definitions, enums, and TypedDicts that form the source of truth for data structures.

Key contracts:
- **EnrichmentStatus** — Canonical lifecycle: none, pending, processing, completed, failed
- **ValidationStatus** — Validation states: pending, valid, invalid
- **EntityAttributesDict** — 11 documented top-level keys in attributes_json
- **Domain Scope** — Parsing and filtering for domain isolation

### [Derived Status Service](derived_status.md)
Tracks build/freshness status of six derived resources: enrichment, graph, semantic_keyword_signals, rag_index, executive_dashboard_snapshot, report_readiness.

Features:
- Read-only status computation without side effects
- 30-second TTL cache with domain + org scoping
- Rebuild endpoint recommendations
- Per-resource status constants (missing, pending, processing, ready, stale, failed, unknown)

### [Entity Query Read-Model](entity_query.md)
Centralised RawEntity query service enforcing three mandatory guards:

1. Exclude synthetic `source = 'graph_materializer'` rows
2. Apply domain-scope filtering via `resolve_domain_filter`
3. Apply org-level isolation via `scope_query_to_org`

Exports: `entity_base_q()`, `count_total()`, `count_by_status()`, `count_enriched()`

## Recent Hardening Changes

### 1. Entity Metadata Contract (Sprint N)
- Added `EnrichmentStatus` and `ValidationStatus` enums
- Documented `EntityAttributesDict` TypedDict with 11 known keys
- Startup migration: legacy "done"/"enriched" → "completed"
- Tests: 21 tests in `test_entity_metadata_contract.py`

### 2. Derived Data Status (Sprint N)
- New service: `backend/services/derived_status_service.py`
- New router: `backend/routers/derived_status.py`
- Frontend panel in `/analytics/dashboard` with rebuild buttons
- Tests: Integrated into analytics test suite

### 3. Read-Model Factory (Sprint N)
- New service: `backend/services/entity_query.py`
- Centralises three mandatory RawEntity query guards
- Migrated routers: entities, analytics, disambiguation, deps
- Tests: 11 tests in `test_entity_query.py`

## Architecture Patterns

- **Domain Scoping** — All queries filtered by domain via `resolve_domain_filter`
- **Org Isolation** — Multi-tenant via `scope_query_to_org` on RawEntity queries
- **Source Tagging** — `source` column identifies data origin (user upload, demo, adapter, graph_materializer)
- **Status Lifecycle** — Clear enum-based state machines for enrichment and validation
- **Read-Only Services** — `DerivedStatusService` computes status without modifying data

## Testing Strategy

- **Unit Tests** — Individual functions and helpers (entity_query, derived_status)
- **Integration Tests** — Full router endpoints with auth, domain, org context
- **Fixture Pattern** — Shared `auth_headers`, `editor_headers`, `viewer_headers` in conftest
- **DB Isolation** — StaticPool in-memory SQLite for test isolation

## File Organization

```
backend/
├── main.py                          # 160-line slim orchestrator
├── models.py                        # SQLAlchemy ORM models
├── schemas.py                       # Pydantic schemas + enums
├── auth.py                          # JWT auth, get_current_user
├── database.py                      # Session management, migrations
├── domain_scope.py                  # Scope parsing + filtering
├── tenant_access.py                 # Org-level isolation helpers
├── services/
│   ├── entity_query.py              # Read-model factory (NEW)
│   ├── derived_status_service.py    # Status computation (NEW)
│   ├── entity_service.py
│   └── ...
├── routers/
│   ├── derived_status.py            # GET /derived-status/* (NEW)
│   ├── entities.py
│   ├── analytics.py
│   ├── disambiguation.py
│   └── ...
└── tests/
    ├── test_entity_metadata_contract.py  (NEW)
    ├── test_entity_query.py              (NEW)
    └── ...
```

## Quick Reference

| Component | Purpose | Key Files |
|-----------|---------|-----------|
| Enrichment Lifecycle | Source-of-truth enum for enrichment states | `schemas.py` |
| Derived Resources | Build status for 6 tracked outputs | `derived_status_service.py` |
| Entity Querying | Safe, scoped RawEntity access | `entity_query.py` |
| Domain Filtering | Scope-aware query constraints | `domain_scope.py` |
| Org Isolation | Multi-tenant row-level security | `tenant_access.py` |
| RBAC | Role-based access control | `auth.py` |

## Next Steps

1. Migrate remaining routers to use `entity_base_q` (check grep for old patterns)
2. Document frontend derived-status panel integration
3. Add schema migration docs for legacy enrichment_status values
4. Expand frontend API documentation with new `/derived-status` endpoints
