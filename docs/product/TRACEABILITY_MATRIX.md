# Traceability Matrix

Matriz viva para conectar estrategia, ejecucion y evidencia.

## Como usarla

Cada fila debe poder seguir este hilo:

`Vision -> Epic -> Historia -> Sprint -> Evidencia tecnica -> Evidencia funcional`

## Matriz inicial

| Vision / Objetivo | Epic | Historia | Sprint | Evidencia tecnica | Evidencia funcional | Estado |
|---|---|---|---|---|---|---|
| Plataforma agnostica de dominio | EPIC-001 | US-001 | SPRINT-102 | `backend/models.py`, `backend/domains/`, `docs/product/epics/EPIC-001-universal-data-engine.md` | Catalogo universal, domains registry | Done |
| Ingesta confiable de datos | EPIC-002 | US-009 | SPRINT-102 | `backend/routers/ingest.py`, `frontend/app/import/`, `docs/product/epics/EPIC-002-ingestion-and-mapping.md` | Import wizard, preview, mapping | Done |
| Calidad y normalizacion | EPIC-003 | US-003 | SPRINT-102 | `disambiguation.py`, `harmonization.py`, `quality.py`, `docs/product/epics/EPIC-003-data-quality-and-harmonization.md` | Disambiguation UI, transformations, quality score | Done |
| Enriquecimiento y autoridad | EPIC-004 | US-011 | SPRINT-102 | `authority.py`, `enrichment_worker.py`, `scrapers.py`, `docs/product/epics/EPIC-004-authority-and-enrichment.md` | Authority review, enrichment stats | Done |
| Inteligencia analitica | EPIC-006 | US-013 | SPRINT-102 | `analytics.py`, `nlq.py`, `olap.py`, `docs/product/epics/EPIC-006-analytics-and-decision-intelligence.md` | Dashboard, NLQ, OLAP explorer | Done |
| AI contextual y RAG | EPIC-007 | US-005 | SPRINT-102 | `ai_rag.py`, `context.py`, `tool_registry.py`, `docs/product/epics/EPIC-007-ai-rag-and-context-engineering.md` | RAG chat, agentic mode | Done |
| Automatizacion y entrega | EPIC-009 | US-015 | SPRINT-102 | `scheduled_reports.py`, `workflows.py`, `alert_channels.py`, `docs/product/epics/EPIC-009-automation-and-delivery.md` | Scheduled reports, workflows, alerts | Done |
| Seguridad y plataforma | EPIC-010 | US-007, US-008 | SPRINT-102 | `auth_users.py`, `api_keys.py`, `audit_log.py`, `docs/DOCUMENTATION_GOVERNANCE.md`, `docs/product/sprints/SPRINT-102.md` | RBAC, API keys, audit log, gobernanza operativa | Done |
| Runtime confiable y reproducible | EPIC-011 | US-039, US-040, US-041 | SPRINT-104 | `requirements.txt`, `backend/database.py`, `backend/main.py`, `docs/product/epics/EPIC-011-hardening-and-runtime-reliability.md` | Runtime mas predecible y mas creible para produccion | Planned |
| Aislamiento real por tenant | EPIC-012 | US-043 | SPRINT-105 | `backend/tenant_scoping.py`, `backend/routers/analytics.py`, `docs/product/TENANT_SCOPING_MODEL.md`, `docs/product/epics/EPIC-012-tenant-isolation-and-access-control.md` | Modelo objetivo y olas de migracion definidos para iniciar tenant isolation real | In progress |
| Credibilidad comercial y tecnica | EPIC-013 | US-046, US-047, US-048 | SPRINT-104 | `README.md`, `backend/routers/onboarding.py`, `backend/enterprise_readiness.py`, `backend/routers/analytics.py`, `frontend/app/components/OnboardingChecklist.tsx`, `frontend/app/components/WelcomeModal.tsx`, `docs/product/COMMERCIAL_MVP.md`, `docs/product/COMPLIANCE_GAP_REGISTER.md`, `docs/product/epics/EPIC-013-commercial-readiness-and-credibility.md` | Foco comercial, onboarding real y baseline de readiness enterprise definidos con evidencia reutilizable | Done |
| Frontend mantenible | EPIC-014 | US-049 | SPRINT-TBD | `EntityTable.tsx`, `Sidebar.tsx`, `RAGChatInterface.tsx`, `docs/product/epics/EPIC-014-frontend-decomposition-and-maintainability.md` | Menor complejidad de UI y mejor velocidad de iteracion | Planned |
| Observabilidad y operacion | EPIC-015 | US-051, US-052, US-053 | SPRINT-104 | `backend/logging_utils.py`, `backend/telemetry.py`, `backend/ops_checks.py`, `backend/routers/analytics.py`, `backend/routers/scheduled_imports.py`, `backend/routers/scheduled_reports.py`, `docs/product/epics/EPIC-015-observability-and-operations.md` | Mejor visibilidad operativa y readiness de producto serio | Done |
| Gobierno de controles | EPIC-018 | ER-CTRL-001 | Unscheduled | `ENTERPRISE_READINESS_PROGRAM.md`, `ENTERPRISE_CONTROL_REGISTER.md` | Registro operado y evidence index versionado | specified |
| Jobs durables | EPIC-018 | US-042 / ER-OPS-001 | Unscheduled | `openspec/changes/external-background-job-runtime/` | 14 dias de SLO, recovery y replay | specified |
| Recovery medido | EPIC-018 | US-073 / ER-BCP-001 | Unscheduled | `docker-compose.prod.yml`, runbooks operativos | Restore drill y RTO/RPO medidos | identified |
| Secure SDLC | EPIC-018 | US-074 / ER-SDLC-001 | Unscheduled | `.github/workflows/security.yml`, `.github/workflows/codeql.yml`, SBOM | 30 dias de gates bloqueantes | implemented |
| Evidencia auditable | EPIC-018 | US-075 / ER-AUD-001 | Unscheduled | `backend/audit.py`, lifecycle events | Pack tenant-scoped verificable | identified |
| Privacy assurance | EPIC-018 | US-076 / ER-PRIV-001 | Unscheduled | `docs/legal/` | Legal review y pack aprobado | specified |
| Identity lifecycle | EPIC-018 | US-077 / ER-IAM-001 | Unscheduled | auth, SSO, API keys, tenant isolation | Offboarding y break-glass drills | identified |
| Residency governance | EPIC-018 | US-078 / ER-DEP-001 | Unscheduled | production compose, topology docs | Region, data-flow y exit evidence | identified |
| Incident response | EPIC-018 | US-079 / ER-IR-001 | Unscheduled | telemetry, ops checks, audit | Tabletop y notification workflow | identified |
| Capacity envelope | EPIC-018 | US-080 / ER-PERF-001 | Unscheduled | load scripts and metrics | Repeatable load report and alerts | identified |
| Independent assurance | EPIC-018 | US-081 / ER-ASSURE-001 | Unscheduled | control evidence packs | Pentest, retest, pilot and exit decision | identified |

## Regla de mantenimiento

Cuando una historia se refine o se complete:

- reemplaza `US-TBD` por su ID real
- reemplaza `SPRINT-TBD` por el sprint real
- enlaza archivos, endpoints o docs relevantes
- actualiza el estado

## Continuidad del backfill

Siguiente recomendacion:

1. descomponer cada epic en historias funcionales pequenas por flujo
2. iniciar releases formales desde el siguiente sprint operativo
3. decidir si se retro-documentan sprints historicos o solo se sigue hacia adelante
