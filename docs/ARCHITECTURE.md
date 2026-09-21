# Arquitectura y Patrones de Ingeniería de Software

## UKIP — Universal Knowledge Intelligence Platform
### Documentación Técnica de Diseño

> **Nota de proveniencia:** Este proyecto se originó como **DB Disambiguador** — una herramienta de higiene de catálogos de productos para e-commerce. A partir de marzo 2026, evolucionó estratégicamente hacia una plataforma de inteligencia de conocimiento agnosótica de dominio. Ver [EVOLUTION_STRATEGY.md](EVOLUTION_STRATEGY.md) para la trazabilidad completa de esta decisión.

> **Nota de alcance (issue #296):** Este documento tiene dos partes con propósitos distintos.
> **Parte I** es el **estado actual, verificado contra el repositorio**: capacidades reales, niveles de soporte, fronteras de código y gates de release. Es la fuente canónica para "qué es UKIP hoy" y para decisiones de arquitectura.
> **Parte II** es un **registro histórico** de los patrones de diseño documentados durante la era DB Disambiguador → UKIP temprano. Se conserva porque explica *por qué* el sistema está construido como está y porque parte de ese código (p. ej. los adaptadores de comercio, §8.4) sigue existiendo en el repositorio aunque ya no sea parte de la superficie de producto actual. Donde una afirmación de la Parte II ya no describe el sistema actual, se corrigió o se marcó explícitamente como histórica — no se preservó por consistencia.

**Última actualización:** 2026-08-23 (issue #296 — capacidades y niveles de soporte)
**Versión del documento:** 4.0

---

## Índice

**Parte I — Arquitectura de Capacidades (estado actual)**

1. [Visión General y Estructura Actual del Monorepo](#1-visión-general-y-estructura-actual-del-monorepo)
2. [Niveles de Soporte (Tiers)](#2-niveles-de-soporte-tiers)
3. [Matriz de Capacidades](#3-matriz-de-capacidades)
4. [Mapas de Frontera: Tier 1 y Tier 2](#4-mapas-de-frontera-tier-1-y-tier-2)
5. [Direcciones de Dependencia entre Capacidades](#5-direcciones-de-dependencia-entre-capacidades)
6. [Release Gates y Capacidades Protegidas](#6-release-gates-y-capacidades-protegidas)
7. [Candidatos a Limpieza de Módulos Acotados (Boundary Debt)](#7-candidatos-a-limpieza-de-módulos-acotados-boundary-debt)

**Parte II — Registro Histórico de Diseño (era DB Disambiguador → UKIP)**

8. [Filosofía de Diseño](#8-filosofía-de-diseño)
9. [Principios SOA Aplicados con Pragmatismo](#9-principios-soa-aplicados-con-pragmatismo)
10. [Modelo de Madurez Evolutiva (histórico)](#10-modelo-de-madurez-evolutiva-histórico)
11. [Arquitectura Cliente-Servidor (histórico)](#11-arquitectura-cliente-servidor-histórico)
12. [Patrones de Diseño (histórico)](#12-patrones-de-diseño-histórico)
13. [Patrones Estructurales (histórico)](#13-patrones-estructurales-histórico)
14. [Patrones de Integración (histórico, sync de tiendas)](#14-patrones-de-integración-histórico-sync-de-tiendas)
15. [Patrones de Frontend](#15-patrones-de-frontend)
16. [Patrones de Datos](#16-patrones-de-datos)
17. [Decisiones Técnicas Clave (histórico, con corrección)](#17-decisiones-técnicas-clave-histórico-con-corrección)
18. [Diagrama de Flujo de Datos (histórico, sync de tiendas)](#18-diagrama-de-flujo-de-datos-histórico-sync-de-tiendas)
19. [Anti-Patrones: Lo Que Decidimos NO Hacer](#19-anti-patrones-lo-que-decidimos-no-hacer)
20. [Guía de Decisión para Nuevas Features](#20-guía-de-decisión-para-nuevas-features)
21. [Principios SOLID Aplicados](#21-principios-solid-aplicados)
22. [Resumen Ejecutivo (histórico)](#22-resumen-ejecutivo-histórico)

---

# Parte I — Arquitectura de Capacidades (estado actual)

## 1. Visión General y Estructura Actual del Monorepo

UKIP (Universal Knowledge Intelligence Platform) es una plataforma de inteligencia de conocimiento agnóstica de dominio: ingesta, normaliza, reconcilia contra fuentes de autoridad, enriquece con evidencia externa, analiza y reporta datos de alto valor — hoy con foco de producto en inteligencia científica e institucional (publicaciones, autores, afiliaciones, organizaciones, conceptos, citas).

*Históricamente fue DB Disambiguador, una herramienta de gestión de catálogo de productos e-commerce. Parte de ese código sigue en el repositorio (§4, capacidad "Integración Comercial Legacy") pero ya no es la superficie de producto principal.*

Este es el árbol real del monorepo, verificado contra el repositorio en la SHA base de este PR (no el árbol de 4 carpetas de la Parte II, que describe una fase anterior):

```
universal-knowledge-intelligence-platform/
├── backend/                    FastAPI API server (Python 3.13 en producción)
│   ├── routers/                 70 módulos de router, ~420 operaciones HTTP documentadas
│   ├── services/                 48 módulos de servicio (lógica de negocio por capacidad)
│   ├── authority/                19 módulos: resolución, scoring, normalización, caché, resolvers
│   ├── analyzers/                 13 analizadores estadísticos: tópicos, correlación, coautoría, geografía…
│   ├── analytics/                 vector store, RAG engine, Monte Carlo — infraestructura RAG (no confundir con analyzers/)
│   ├── adapters/
│   │   ├── enrichment/            8 adaptadores de enriquecimiento científico (OpenAlex, Crossref, PubMed…)
│   │   ├── scientific/            6 adaptadores de importación de literatura (arXiv, DataCite, ORCID, Zotero…)
│   │   ├── llm/                   3 adaptadores de proveedor LLM (Anthropic, OpenAI, local)
│   │   └── commerce/               adaptadores de comercio heredados (WooCommerce/Shopify/Bsale/Custom) — ver §4/§7
│   ├── retrospective/             8 módulos: historia append-only, snapshots, export, métricas (ADR-006)
│   ├── jobs/                       7 módulos: runtime de cola durable en PostgreSQL (ADR-007)
│   ├── cache/                     capa de caché distribuida: Redis + fallback in-process
│   ├── domains/                   3 esquemas configurables: default, science, healthcare
│   ├── eval/                      harness de evaluación de calidad de resolución de entidades
│   ├── tests/                     311 archivos de test, ~3985 tests recolectados (ver docs/generated/repo_metrics.json)
│   └── *.py (41 módulos top-level) auth, encryption, tenant_*, enterprise_*, workflow_engine, report_builder…
├── frontend/                    Next.js App Router (React 19 / TypeScript)
│   ├── app/                       ~28 superficies de producto con page.tsx, 55+ componentes, 8 context providers
│   └── app/i18n/                  catálogo EN/ES, proyectado a backend/i18n/ (issue #269)
├── engine/                      Motor Rust gRPC — aceleración opcional para grafos y texto a gran escala
├── sdk/                         Clientes generados (Python + TypeScript) + sdk/openapi.json (contrato committeado)
├── alembic/                     Migraciones de base de datos (PostgreSQL en producción)
├── openspec/                    Especificaciones de capacidad por feature y cambios activos (granularidad de feature, no de capacidad — ver nota abajo)
├── docs/                        Arquitectura, producto, operación, onboarding
├── docker/                      Entrypoints de contenedor
└── scripts/                     Utilidades de mantenimiento, generadores, linters de gobernanza (#293/#294/#295)
```

**Relación con `openspec/`:** `openspec/specs/` (43 specs) y `openspec/changes/` documentan comportamiento a nivel de *feature* (p. ej. `crossref-adapter`, `enrichment-cascade-config`, `derived-data-status-api`). Este documento opera a nivel de *capacidad* (agrupaciones más amplias, con nivel de soporte y frontera de código). Los dos no compiten: una capacidad de la Parte I puede tener varias specs de OpenSpec debajo. Este PR no crea un tercer registro — la matriz de §3 es la única fuente canónica de niveles de soporte.

**Relación con `docs/product/ENTERPRISE_CONTROL_REGISTER.md`:** ese registro mide la madurez de **controles operacionales transversales** (backup/DR, IAM, incident response, supply chain) en una escala `identified → specified → implemented → verified → operated → auditable`. Los **niveles de soporte** de este documento miden algo distinto: cuánta protección de release y compromiso de estabilidad tiene cada **capacidad de producto**. Un control puede estar `specified` en el registro de enterprise-readiness mientras la capacidad de producto que protege es Tier 1 aquí — son ejes ortogonales, no contradictorios.

---

## 2. Niveles de Soporte (Tiers)

Los cuatro niveles del issue #296, hechos operacionalmente verificables. La asignación de cada capacidad en §3 se basa en evidencia del repositorio — nunca en intuición.

**Regla de precedencia (correcta tras revisión estratégica del 2026-08-23):** el tier de una capacidad lo determina, en este orden, su **criticidad de producto/operación, compromiso de soporte, expectativa de estabilidad/compatibilidad e impacto de falla** — no la topología actual de CI. Los gates de CI y la madurez de `ENTERPRISE_CONTROL_REGISTER.md` son **evidencia de apoyo y protección observada**, nunca el criterio que define el tier. Dos consecuencias explícitas:

- Una capacidad Tier 1 puede existir sin gate de CI dedicado hoy — en ese caso se documenta como **brecha de protección** (§6) y es candidata prioritaria a mejorar cobertura, pero no pierde el tier.
- Una capacidad Tier 3 puede tener un gate de seguridad/calidad dedicado (p. ej. escaneo de imagen Docker) sin convertirse automáticamente en Tier 1 — el gate protege un riesgo específico de esa capacidad, no implica compromiso de estabilidad de producto.
- La madurez de un control de `ENTERPRISE_CONTROL_REGISTER.md` asociado a una capacidad es un **eje ortogonal** (ver §1, "Relación con..."): un control por debajo de `implemented` no descalifica a una capacidad de Tier 1/2; se documenta como deuda/riesgo de aseguramiento operacional explícito en la fila de la capacidad y, cuando aplica, en §6.

### Tier 1 — Core Product / Release-Blocking

| Dimensión | Definición |
| --- | --- |
| Estado de usuario/operación | Ejercitada por todo flujo real de tenant en producción; su falla bloquea o corrompe el loop principal del producto (ingesta → dato canónico → autoridad → enriquecimiento → analítica/reporte) o la superficie de seguridad/contrato de la plataforma. |
| Expectativa de compatibilidad | Contratos públicos (rutas API, operaciones OpenAPI, superficie de SDK, schema de BD que la capacidad posee) son estables; un cambio incompatible requiere ADR o plan de versionado explícito. |
| Protección de test/release esperada | **Objetivo**, no requisito de admisión: se espera la protección de CI más fuerte disponible — idealmente un gate bloqueante dedicado más allá de la suite general (p. ej. el gate F1 de resolución de entidades, la corrida exhaustiva contra PostgreSQL, el smoke de SDK con auth+scope real, `frontend-e2e-critical`, los gates de drift de OpenAPI/SDK). Si una capacidad Tier 1 no tiene hoy ese gate dedicado, permanece Tier 1 por su criticidad de producto y la ausencia se registra como **brecha de protección** en §6 — no descalifica. |
| Obligación de documentación | Debe tener mapa de frontera explícito (§4), fila de release-gate (§6) con su brecha de protección documentada si existe, y reflejarse en los hechos generados del README (#295) cuando aplique. |
| Expectativa de incidente/soporte | Incidentes de producción que la afectan son severidad 1/2 por defecto. La madurez de los controles P0/P1 de `ENTERPRISE_CONTROL_REGISTER.md` que la tocan se registra como eje de aseguramiento operacional aparte (ver nota de precedencia arriba) — no cambia el tier. |
| Qué NO califica | Capacidades sin las cuales el producto sigue funcionando (opcionales/con fallback); herramientas admin internas sin contrato de cliente; cualquier cosa documentada explícitamente como legacy. La protección de CI, por sí sola, **ni otorga ni quita** Tier 1. |

### Tier 2 — Production-Supported

| Dimensión | Definición |
| --- | --- |
| Estado de usuario/operación | Funcionalidad real, shipeada, usable por clientes; parte del feature set documentado, pero no es ella misma la que bloquea cada release. |
| Expectativa de compatibilidad | Se espera que el contrato se mantenga estable de release a release; un cambio incompatible debe señalarse en `CHANGELOG.md`, no shipearse en silencio. |
| Protección de test/release esperada | Cubierta por la suite exhaustiva general de backend (shards + partition-union guard, #293) y/o la suite Vitest de frontend; un gate dedicado propio no es requisito de Tier 2 (eso es un plus de Tier 1). |
| Obligación de documentación | Mapa de frontera requerido (§4); aparece en la matriz (§3) con ubicación de código y dependencias. |
| Expectativa de incidente/soporte | Bugs de producción se triage y corrigen en el cadence normal de release; no es severidad-1 automática salvo que involucre integridad de datos o seguridad. |
| Qué NO califica | Capacidades detrás de un flag que hoy por defecto está apagado en la topología de producción real (verificable, no supuesto — ver ejemplo en §3, Cola de jobs durable) y sin evidencia de cutover (eso es Tier 3); herramientas admin-only sin contrato de cliente (Tier 3). **La madurez de un control de `ENTERPRISE_CONTROL_REGISTER.md` asociado no descalifica por sí sola** — si está por debajo de `implemented`, se documenta como deuda/riesgo de aseguramiento en la fila de la capacidad (ver nota de precedencia arriba). |

### Tier 3 — Experimental

| Dimensión | Definición |
| --- | --- |
| Estado de usuario/operación | Código real, funcionando, ejercitado en producción o disponible para algunos tenants, pero el producto funciona completamente sin ella (opcional/con fallback), o su radio de impacto es intencionalmente angosto (admin-only, detrás de flag, dependiente de LLM con guardrails de gobernanza). |
| Expectativa de compatibilidad | El contrato puede cambiar sin ADR; los consumidores no deben asumir estabilidad de largo plazo. |
| Protección de test/release | Cubierta solo por la suite general donde exista; puede tener gate de CI dedicado (p. ej. escaneo de imagen Docker) sin que eso cambie su tier — el gate protege un riesgo puntual de esa capacidad, no un compromiso de estabilidad de producto. |
| Obligación de documentación | Mapa de frontera opcional pero recomendado; debe listarse en la matriz con justificación explícita de "por qué Tier 3". |
| Expectativa de incidente/soporte | Best-effort; una falla no es automáticamente severidad-1. |
| Qué NO califica | Cualquier cosa de la que dependa el loop ingesta→canónico→autoridad→enriquecimiento para operar (eso es Tier 1 por criticidad, sin importar su cobertura de CI actual — ver brechas de protección en §6); cualquier cosa con compromiso de soporte/cliente estable y evidencia real de uso en producción (eso es Tier 2). **Tener un gate de CI dedicado no vuelve Tier 1 a una capacidad Tier 3.** |

### Tier 4 — Research/Incubating

| Dimensión | Definición |
| --- | --- |
| Estado de usuario/operación | Exploratorio; puede estar incompleto; puede eliminarse sin aviso; no forma parte de ningún compromiso con clientes. |
| Expectativa de compatibilidad | Ninguna asumida. |
| Protección de test/release | Ninguna requerida más allá de "no romper el build". |
| Obligación de documentación | Una fila de una línea en la matriz es suficiente. |
| Expectativa de incidente/soporte | Ninguna. |
| Qué NO califica | Cualquier cosa con una ruta orientada a cliente de la que dependa un tenant pagante hoy (eso es al menos Tier 3). |

---

## 3. Matriz de Capacidades

Cada capacidad tiene **exactamente un** nivel de soporte. Método de inventario: se enumeraron `backend/routers/` (70 módulos), `backend/services/` (48), `backend/authority/`, `backend/analyzers/`, `backend/adapters/*`, `backend/retrospective/`, `backend/jobs/`, `backend/cache/`, los 41 módulos top-level de `backend/`, `frontend/app/` (28 superficies), `sdk/`, y se cruzó contra `.github/workflows/*.yml`, `docs/adr/*`, `docs/product/epics/*`, `docs/product/ENTERPRISE_CONTROL_REGISTER.md` y `docs/operating/*`. Los docstrings de cada router se leyeron para confirmar propósito real (no solo el nombre del archivo).

**Cómo leer la columna "Evidencia de tier":** combina, sin distinguir tipográficamente, la razón de criticidad/soporte que en realidad determina el tier (§2) con la evidencia de CI/gates que la respalda. La evidencia de CI es apoyo observado, no el criterio de asignación — donde esa evidencia es más débil de lo esperado para el tier, la fila lo señala explícitamente y el caso se repite en la lista de brechas de protección (§6).

### Grupo A — Pipeline principal del producto

| Capacidad | Tier | Responsabilidad | Código principal | Almacenamiento/runtime | Contrato principal | Evidencia de tier |
| --- | --- | --- | --- | --- | --- | --- |
| **Ingesta y adaptadores de origen** | 1 | Subir CSV/Excel/API, perfilar fuentes, mapear columnas, importar literatura científica | `backend/routers/{ingest,ingest_helpers,api_import,scientific_import,column_maps,scheduled_imports,external_attention,scrapers}.py`, `backend/adapters/scientific/`, `backend/services/source_profiler.py` | PostgreSQL (`RawEntity` origen) | REST `/upload`, `/import/*`, `/scientific/*` | **Tier 1 por criticidad de producto**: es el primer paso obligatorio del loop core (§5) — su falla bloquea todo lo demás. Cobertura de CI: solo shards+`postgres-shard` (suite general); **sin gate bloqueante dedicado propio → brecha de protección documentada en §6** |
| **Dato canónico y CRUD de entidades** | 1 | Modelo `RawEntity`, CRUD, scoring de calidad, estado derivado | `backend/routers/{entities,quality,derived_status}.py`, `backend/services/{entity_service,entity_query,derived_status_service}.py`, `backend/quality_scorer.py`, `backend/models.py` | PostgreSQL | `entity_base_q` (factory interna), REST `/entities/*` | `entity-query-lint` gate dedicado; base de `eval-quality` |
| **Resolución de autoridad e identidad** | 1 | Reconciliación contra fuentes de autoridad, dedupe, scoring de confianza, feedback loop | `backend/authority/` (19 módulos), `backend/routers/{authority,authority_institutions,authority_records,disambiguation}.py`, `backend/services/{authority_candidate_extraction,authority_promotion,authority_readiness,institution_authority,institution_reconciliation}.py` | PostgreSQL | REST `/authority/*`; ADR-003 | Gate F1 dedicado (`eval-quality`, umbral ≥0.75) |
| **Enriquecimiento científico (proveedores externos)** | 2 | Enriquecer entidades con evidencia externa (OpenAlex, Crossref, PubMed, WoS, Scopus, Semantic Scholar, DBLP, DOAJ, Scholar) | `backend/adapters/enrichment/` (8), `backend/enrichment_worker.py`, `backend/services/enrichment_scheduler.py`, `backend/routers/enrichment_schedule.py`, `backend/circuit_breaker.py` | PostgreSQL, APIs externas | Interfaz `BaseEnrichmentAdapter`; ADR-004 (circuit breaker) | Suite general (#293); sin gate dedicado propio |
| **Gobernanza de datos, harmonización y transformación** | 2 | Reglas de normalización/harmonización con undo/redo, correspondencia de campos entre dominios, motor de expresiones de transformación | `backend/routers/{harmonization,transformations,governance_field_correspondence,governance_field_correspondence_ops,governance_sources,domains}.py`, `backend/services/{field_correspondence,mapping_suggestions,domain_neutral_labels,source_terminology}.py` | PostgreSQL | REST `/harmonization/*`, `/transformations/*`, `/field-correspondence-rules` | Suite general; ver §7 (sin paquete propio, a diferencia de authority/) |
| **Analítica, métricas y grafo de conocimiento** | 2 | Modelado de tópicos, correlación, coautoría, geografía, tendencias, métricas de journal, grafo de entidades | `backend/analyzers/` (13), `backend/routers/{analytics,analytics_analyzers,analytics_ops,coauthorship,graph_export,relationships,journals}.py`, `backend/services/{analytics_service,graph_materializer,researcher_topic_analytics,journal_metrics_service,journal_backfill,impact_projection,pattern_discovery}.py` | PostgreSQL, DuckDB (lake OLAP) | REST `/analytics/*`, `/analyzers/*` | Suite general; DuckDB lake tiene admin read-only propio |
| **Inteligencia retrospectiva** | 2 | Historia append-only, snapshots punto-en-el-tiempo, comparación actual-vs-previo, export a warehouse | `backend/retrospective/` (8 módulos), `backend/routers/retrospective.py` | PostgreSQL (eventos append-only) | REST `/retrospective/*`; ADR-006 (bounded context) | **Tier 2 confirmado por evidencia concreta de activación en producción** (revisión estratégica 2026-08-23, a diferencia del caso de Cola de jobs durable arriba): `docker-compose.prod.yml` línea 107 declara `UKIP_RETRO_EVENTS: ${UKIP_RETRO_EVENTS:-1}` en el bloque real del servicio backend, con el comentario explícito "Default ON in prod so governed history is captured". `backend/retrospective/emit.py` confirma que el flag por defecto en el *código* es OFF (`os.environ.get("UKIP_RETRO_EVENTS", "0")`), pero la topología de producción committeada lo sobreescribe a `1` — el default operacional real es ON, no el default de código. Las APIs de lectura (`/retrospective/*`) y el pipeline de escritura de eventos están ambos activos en producción |
| **Reporte y generación de artefactos** | 2 | Exportes HTML/PDF/Excel, dashboards custom, portales de catálogo, widgets embebibles, deck ejecutivo | `backend/routers/{reports,artifacts,dashboards,widgets,sales_deck,catalogs}.py`, `backend/report_builder.py`, `backend/services/{decision_readout,audience_presets,evidence_traceability,provenance_ui_semantics}.py` | PostgreSQL | REST `/export`, `/exports/*` | **Único de este grupo con smoke de runtime en imagen Docker** (renderizado de PDF real en `docker.yml`) |
| **Agentic / RAG / NLQ** | 3 | Chat de investigación agentic, búsqueda semántica (ChromaDB), consulta en lenguaje natural, skills RAG gobernadas | `backend/routers/{ai_rag,agentic_chat,nlq,assistant_actions,context}.py`, `backend/services/{agentic_research_chat,rag_skill_execution,rag_skill_registry,rag_skill_router,rag_skills_library}.py`, `backend/{llm_agent,context_engine,tool_registry}.py`, `backend/services/genai_governance.py`, `backend/analytics/{rag_engine,vector_store}.py`, `backend/adapters/llm/` | ChromaDB, PostgreSQL, proveedores LLM externos | REST `/ai-integrations`, `/rag/*`, `/nlq` | Dependiente de LLM externo; gobernado explícitamente por ADR-005 y `genai_governance.py`; producto funciona sin ella |

### Grupo B — Plataforma, seguridad y ejecución en background

| Capacidad | Tier | Responsabilidad | Código principal | Almacenamiento/runtime | Contrato principal | Evidencia de tier |
| --- | --- | --- | --- | --- | --- | --- |
| **Auth, RBAC, API keys, SSO y audit** | 1 | Login JWT, roles (super_admin/admin/editor/viewer), llaves de API de larga duración con scopes, SSO vía Authlib, audit log | `backend/{auth,api_key_scopes,encryption,secret_rotation,bootstrap}.py`, `backend/routers/{auth_users,api_keys,audit_log,platform_auth_settings,onboarding}.py` | PostgreSQL | REST `/auth/token`, `/users/*`, `/api-keys/*`; contrato de scopes | Verificada en vivo por `sdk-smoke` (auth + scope-403); `security` marker en tests |
| **Multi-tenancy y aislamiento de dominio** | 1 | Scoping de queries por organización y por dominio (`default`/`science`/`healthcare`) | `backend/{domain_scope,tenant_access,tenant_scoping,tenant_quotas}.py`, `backend/routers/{organizations,domains}.py`, `backend/domains/*.yaml` | PostgreSQL | Filtros `resolve_domain_filter`/`scope_query_to_org` | `domain-scope-lint` gate dedicado |
| **Cola de jobs durable en background (ADR-007)** | 3 | FSM de jobs, claim/lease/retry, worker, scheduler, migración incremental fuera del proceso web | `backend/jobs/` (7 módulos), `backend/routers/jobs.py` | PostgreSQL (lease queue, broker-free) | REST `/jobs/*`; ADR-007 | **Reclasificada de Tier 2 a Tier 3 tras verificar evidencia real de cutover** (revisión estratégica 2026-08-23): `backend/jobs/migration.py::job_mode()` lee `UKIP_JOBS_<DOMAIN>` con default `JobMode.OFF`, y su propio docstring dice "merging changes nothing in production until a mode is deliberately set"; `docker-compose.prod.yml` **no define ningún `UKIP_JOBS_<DOMAIN>`**. Es decir: en la topología de producción committeada, el runtime durable está implementado, testeado y documentado (ADR + runbook + topología + checklist de cutover) pero **no ejecuta nada hoy** — cada dominio (`report`, `import`, `enrichment`) sigue corriendo por su mecanismo in-process preexistente. Consistente con `ER-OPS-001` en el registro de enterprise-readiness: prioridad P1, madurez `specified` (no `operated`), brecha de evidencia "Queue runtime, recovery tests, observation window". El código y el mecanismo de rollout en sí son Tier 3 (experimental, real, detrás de flag, producto funciona sin él); los dominios de negocio que eventualmente correrán sobre él (reporte=Tier 2, ingesta=Tier 1, enriquecimiento=Tier 2) mantienen su propio tier vía su mecanismo actual — ver §4 |
| **Lifecycle de datos y privacidad (EPIC-016)** | 2 | Export DSAR, retención, borrado con evidencia | `backend/routers/data_lifecycle.py`, `backend/services/data_lifecycle.py` | PostgreSQL | REST `/admin/data-lifecycle/*` | `ENTERPRISE_CONTROL_REGISTER.md`: "implemented and tested" |
| **Notificaciones, webhooks, alertas y realtime** | 2 | Entrega de webhooks con historial/audit, canales de alerta (Slack/Teams/Discord), notificaciones in-app, WebSocket | `backend/routers/{webhooks,alert_channels,notifications,ws}.py` | PostgreSQL | REST + WS `/ws` | Suite general |
| **Motor de automatización de workflows** | 2 | Definición y ejecución de workflows automatizados | `backend/routers/workflows.py`, `backend/workflow_engine.py` | PostgreSQL | REST `/workflows/*` | Suite general |
| **Colaboración y anotaciones** | 2 | Anotaciones colaborativas sobre entidades/registros de autoridad | `backend/routers/annotations.py` | PostgreSQL | REST `/annotations/*` | Suite general |
| **Búsqueda** | 2 | Búsqueda full-text a través de entidades, autoridad y anotaciones | `backend/routers/search.py` | PostgreSQL | REST `/search` | Suite general |
| **Backup assurance y disaster recovery** | 2 | Runbook de backup, verificación de integridad, endpoints de metadata admin | `backend/{backup_assurance,backup_assurance_ddl}.py`, `backend/routers/backup_ops.py` | PostgreSQL, storage externo (S3-compatible) | REST `/admin/backup/*` | **Tier 2 justificado por soporte de producto real** (código + runbook implementados, cubiertos por la suite general) — **separado explícitamente de su madurez de aseguramiento**, que es menor: `ER-BCP-001` en el registro está en `specified`, no `operated`; faltan configuración del proveedor, dos ciclos de backup exitosos y el primer drill de restore aislado. Esta fila documenta la brecha para no confundir "el código de backup existe y está soportado" con "la recuperación ante desastre está probada" — ver también §6 |
| **Enterprise readiness y gobernanza de controles** | 2 | Proyección runtime de brechas comerciales conocidas; contrato de paridad con el registro de controles | `backend/{enterprise_readiness,enterprise_controls}.py` | PostgreSQL | REST `/enterprise-readiness`; `ENTERPRISE_CONTROL_REGISTER.md` | Documentado extensamente; la proyección runtime nunca reemplaza el registro (§10 de `DOCUMENTATION_GOVERNANCE.md`) |
| **Personalización de tenant, branding y onboarding** | 2 | Branding white-label, flujo de onboarding, ajustes de auth de plataforma | `backend/routers/{branding,onboarding,platform_auth_settings}.py` | PostgreSQL | REST `/branding/*` (endpoint público) | Suite general; `branding` es público por diseño (necesario antes de login) |

### Grupo C — Herramientas internas, legacy e investigación

| Capacidad | Tier | Responsabilidad | Código principal | Por qué este tier |
| --- | --- | --- | --- | --- |
| **Herramientas operacionales de admin** | 3 | Correcciones de datos ad-hoc, lectura admin del lake OpenAlex/DuckDB, reset de workspace | `backend/routers/{admin_data_fixes,openalex_lake_admin,workspace_reset,workspace_reset_ops}.py` | Admin-only, sin contrato de cliente; radio de impacto angosto por diseño |
| **Demo y habilitación comercial** | 4 | Dataset de demo, deck de ventas ejecutivo | `backend/routers/{demo,sales_deck}.py`, `scripts/generate_demo_dataset.py` | No forma parte del loop de producto para clientes reales; usada para ventas/demos |
| **Integración comercial legacy (pre-pivot)** | 3 | Sync de tiendas e-commerce (WooCommerce/Shopify/Bsale/Custom) heredado de la era DB Disambiguador | `backend/adapters/commerce/` (4 adaptadores), `backend/routers/stores.py`, `models.StoreConnection` | Código real, testeado (16 archivos de test lo ejercitan), pero **fuera de la superficie de producto actual** descrita en la §1 de este PR/issue. Ver §7 — candidato a limpieza de frontera, no a eliminación inmediata |
| **Motor Rust gRPC (aceleración)** | 3 | Aceleración opcional para operaciones de grafo/texto a gran escala | `engine/`, `backend/services/{engine_bridge,engine_client,engine_delegation}.py`, `backend/routers/engine.py` | README: "el motor es opcional; la plataforma opera completamente sin él"; `ENGINE_FALLBACK_PYTHON` prueba el fallback en `sdk-smoke`. Tiene gate de imagen Docker (Trivy+SBOM) pero no es funcionalmente release-blocking |
| **CLI, mantenimiento y migraciones** | 2\* | Scripts de backfill, generadores SDK/i18n, migraciones Alembic, linters de gobernanza | `scripts/`, `alembic/`, `backend/scripts/` | \*Heterogéneo: las migraciones Alembic son Tier 1 de facto (cada `postgres-shard` corre `alembic upgrade head` como gate bloqueante, una vez por shard aislado, sobre una base vacía; `migration-rehearsal` las ejecuta además sobre datos, #361); el resto de scripts de mantenimiento son Tier 2/3 según uso |

### Grupo D — Infraestructura transversal y contrato externo

| Capacidad | Tier | Responsabilidad | Código principal | Contrato principal | Evidencia de tier |
| --- | --- | --- | --- | --- | --- |
| **Persistencia y runtimes de datos** | 1 | PostgreSQL (producción), SQLite (test/local), DuckDB (OLAP), ChromaDB (RAG), Redis (cache distribuida) | `backend/database.py`, `backend/olap.py`, `backend/cache/`, `Dockerfile.backend` (Python 3.13-slim) | Todas las capacidades dependen de al menos una | los 6 `postgres-shard` cubren en conjunto (unión probada, #293) la suite exhaustiva contra Postgres real; los `test-shard` de Python 3.13 corren contra SQLite en memoria |
| **SDK y superficie de contrato OpenAPI** | 1 | Clientes Python/TypeScript generados, spec OpenAPI committeada | `sdk/openapi.json`, `sdk/python/`, `sdk/typescript/`, `scripts/generate-sdk*.{mjs,sh}` | Contrato OpenAPI (~420 operaciones HTTP, ver `docs/generated/repo_metrics.json`) | `openapi-drift` + `sdk-clients-drift` + `sdk-smoke` (auth+scope real) — los tres bloqueantes |
| **Shell de aplicación frontend y superficies de producto** | 1 | App Router de Next.js, ~28 superficies de página, 8 context providers, i18n EN/ES | `frontend/app/` | Contrato de fetch JSON contra la API REST | `frontend-test`, `frontend-typecheck`, `frontend-lint`, `design-system:check`, `frontend-e2e-critical` (Playwright `@critical`) |
| **Ingeniería de release y gobernanza del repositorio** | 1 | Partición determinística de tests (#293), ratchet de deuda de lint (#294), métricas generadas del repo (#295), gates de OpenAPI/SDK/i18n/dominio/seguridad | `scripts/{backend_test_partitions,lint_debt_ratchet,lint_backend_changed,lint_domain_scope,lint_entity_query,generate_repo_metrics}.py`, `.github/workflows/*.yml` | Es en sí misma el conjunto de gates bloqueantes que protege a todas las demás capacidades | Por construcción: cada gate es bloqueante para todo PR |

**Total: 29 capacidades — 9 Tier 1, 14 Tier 2, 5 Tier 3, 1 Tier 4.** ("CLI, mantenimiento y migraciones" cuenta como Tier 2 pese a su nota heterogénea — las migraciones Alembic son Tier 1 de facto dentro de esa fila, pero la fila en sí es Tier 2. "Cola de jobs durable" cuenta como Tier 3 tras la reclasificación de esta revisión — ver fila arriba y §6.)

---

## 4. Mapas de Frontera: Tier 1 y Tier 2

Para cada capacidad Tier 1/2: qué pertenece dentro, qué debe quedar fuera, dirección de dependencia permitida, contrato usado a través de la frontera, y dónde se tolera acoplamiento cruzado hoy (y por qué). Se incluye también "Cola de jobs durable (ADR-007)" pese a su reclasificación a Tier 3 en §3 — su mapa de frontera sigue siendo útil dado que es el sustrato de ejecución compartido hacia el que varias capacidades Tier 1/2 están migrando activamente.

| Capacidad | Dentro de la frontera | Fuera de la frontera | Dirección de dependencia permitida | Contrato a través de la frontera | Acoplamiento tolerado hoy |
| --- | --- | --- | --- | --- | --- |
| Ingesta y adaptadores de origen | Parseo de archivos, perfilado de fuentes, adaptadores de importación científica, mapeo de columnas | Lógica de resolución de autoridad, enriquecimiento, analítica | → escribe `RawEntity` (dato canónico); no depende de autoridad/enriquecimiento/analítica | Filas `RawEntity` con `enrichment_status=none` | Ninguno documentado — frontera limpia |
| Dato canónico y CRUD de entidades | `RawEntity`, `entity_base_q`, scoring de calidad, estado derivado | Reglas de negocio de autoridad/enriquecimiento específicas | Depende de Multi-tenancy (scoping); todo lo demás depende de esta capacidad, no al revés | `entity_base_q(db, scope, org_id)` (factory de query segura) | `derived_status_service` re-deriva estado leyendo ~6 tipos de recurso de otras capacidades (autoridad, enriquecimiento, harmonización…) — es un agregador de lectura legítimo, pero es el punto de mayor "fan-in" del sistema; ver §7 |
| Resolución de autoridad e identidad | Motor de resolución (`backend/authority/`), candidatos, promoción, scoring, feedback | Persistencia directa de reglas de harmonización | Lee `RawEntity`; escribe `AuthorityRecord`; no depende de enriquecimiento/analítica | REST `/authority/*`; ADR-003 | Lógica de "autoridad" está repartida entre `backend/authority/` (motor), `backend/services/authority_*.py` y `backend/services/institution_*.py` (flujos de producto) y 3 routers — ver §7, candidato de consolidación |
| Enriquecimiento científico | Adaptadores externos, worker de background, scheduler de staleness | Lógica de resolución de identidad | Lee `RawEntity`; escribe `attributes_json`; no decide identidad (eso es autoridad) | Interfaz `BaseEnrichmentAdapter`; ADR-004 (circuit breaker) | El scheduler de staleness (`enrichment_scheduler.py`) sigue como loop asyncio propio, fuera de la cola durable ADR-007 que ya cubre `enrichment.execute` job-a-job — migración incremental documentada, no completada |
| Gobernanza de datos, harmonización y transformación | Reglas de harmonización con undo/redo, correspondencia de campos, motor de expresiones | Resolución de identidad, enriquecimiento externo | Lee/escribe `RawEntity` y reglas propias; no llama adaptadores externos | REST `/harmonization/*`, `/field-correspondence-rules` | Sin paquete Python dedicado (a diferencia de `authority/`/`analyzers/`/`retrospective/`) — la lógica vive repartida en 3 routers + 4 servicios + `harmonization.py`/`transformations.py`; ver §7 |
| Analítica, métricas y grafo de conocimiento | Analizadores estadísticos, materialización de grafo, métricas de journal | Escritura de dato canónico | Solo lectura de `RawEntity`/`AuthorityRecord`; escribe agregados propios | REST `/analytics/*`, `/analyzers/*` | `backend/analytics/` (RAG/vector) y `backend/analyzers/` (estadística) tienen nombres casi idénticos pero son paquetes no relacionados — riesgo de confusión de import, no de acoplamiento real; ver §7 |
| Inteligencia retrospectiva | Emisión de eventos append-only, snapshots, export a warehouse | Mutación de estado actual (solo lee) | Suscribe eventos de otras capacidades; nunca escribe de vuelta al dato canónico | ADR-006 (bounded context); export a warehouse vía `UKIP_WAREHOUSE_DATASET` | Ninguno documentado — bounded context explícito por ADR. `UKIP_RETRO_EVENTS` confirmado en `1` (ON) en `docker-compose.prod.yml` — a diferencia de la Cola de jobs durable, este flag sí está activo en la topología de producción committeada |
| Reporte y generación de artefactos | Construcción de HTML/PDF/Excel, dashboards, portales, widgets | Cálculo de analítica (consume resultados, no los recalcula) | Lee de Analítica/Autoridad/Retrospectiva; no escribe dato canónico | REST `/export`, `/exports/*`; `report_builder.py` | Sin paquete dedicado, igual que Gobernanza — routers/servicios repartidos (`reports`,`artifacts`,`sales_deck`,`dashboards`,`widgets` + 4 servicios); menor prioridad que Gobernanza porque las salidas son legítimamente heterogéneas |
| Auth, RBAC, API keys, SSO y audit | Autenticación, autorización, scopes de API key, audit trail | Lógica de negocio de cualquier otra capacidad | Todas las demás capacidades dependen de esta vía `Depends(get_current_user)`/`require_role`; no depende de ninguna | JWT; contrato de scopes de API key | Ninguno documentado — frontera limpia y bien testeada (`sdk-smoke`) |
| Multi-tenancy y aislamiento de dominio | Scoping por org y por dominio | Lógica de negocio específica de cada capacidad | Todas las demás capacidades pasan por `resolve_domain_filter`/`scope_query_to_org`; no depende de ellas | Filtros de query compartidos | Ninguno documentado — `domain-scope-lint` lo hace cumplir |
| Cola de jobs durable (ADR-007) | FSM de jobs, claim/lease/retry, handlers registrados | Lógica de negocio de cada dominio (delega a `enrichment_worker`, `scheduled_imports`, etc.) | Otras capacidades encolan trabajo; el runtime no conoce el dominio de negocio más allá del handler registrado | `runtime.register_handler(name, fn)`; ADR-007 | Handlers registrados para `report`/`import`/`enrichment` (código listo para cutover), pero `UKIP_JOBS_<DOMAIN>` no está seteado en `docker-compose.prod.yml` — ningún dominio está en modo `queue` en producción hoy; el scheduler de staleness ni siquiera tiene handler registrado. Ver §3 para la reclasificación de tier que esto motivó |
| Lifecycle de datos y privacidad | Export DSAR, retención, borrado | — | Lee de todas las capacidades con datos de tenant; no las modifica salvo al ejecutar borrado autorizado | REST `/admin/data-lifecycle/*` | Ninguno documentado |
| Notificaciones, webhooks, alertas y realtime | Entrega, historial, canales | Lógica de negocio que dispara el evento | Consume eventos de otras capacidades; no las modifica | REST + WS | Ninguno documentado |
| Motor de automatización de workflows | Definición y ejecución de workflows | Lógica específica de cada capacidad que el workflow orquesta | Puede invocar operaciones de otras capacidades vía sus contratos públicos | REST `/workflows/*` | Por diseño, un motor de workflow cruza capacidades — el límite es que solo invoca contratos públicos, no estado interno |
| Colaboración y anotaciones | Anotaciones sobre cualquier entidad/registro | — | Referencia IDs de otras capacidades; no las modifica | REST `/annotations/*` | Ninguno documentado |
| Búsqueda | Índice/consulta full-text | — | Solo lectura a través de capacidades indexadas | REST `/search` | Ninguno documentado |
| Backup assurance y DR | Runbook, verificación de integridad | — | Opera sobre el almacenamiento de Persistencia; no conoce lógica de negocio | REST `/admin/backup/*` | Madurez operacional (no de código) por debajo del tier — ver Grupo B |
| Enterprise readiness y gobernanza de controles | Proyección runtime de brechas | — | Lee metadata de estado de otras capacidades; nunca es la autoridad de estado (`DOCUMENTATION_GOVERNANCE.md` §10) | REST `/enterprise-readiness` | Ninguno documentado |
| Persistencia y runtimes de datos | Motores de BD, caché, sesión | Lógica de negocio | Todas las capacidades dependen de esta; no depende de ninguna | `DATABASE_URL`, `SessionLocal`/`get_db` | Ninguno documentado |
| SDK y superficie de contrato OpenAPI | Clientes generados, spec committeada | Implementación de los routers (solo los describe) | Se deriva de los routers vía `scripts/generate-sdk*`; nunca al revés | `sdk/openapi.json` | Ninguno documentado — gates de drift lo hacen cumplir |
| Shell de aplicación frontend | Páginas, componentes, contexts, i18n | Lógica de negocio del backend | Consume la API REST vía JSON; no conoce SQLAlchemy/Python | Shapes de JSON documentados en OpenAPI | Ninguno documentado |
| Ingeniería de release y gobernanza del repo | Scripts de gates, workflows de CI | Lógica de producto | Ninguna capacidad depende de esta para funcionar en runtime; todas dependen de ella para *shippear* | Exit codes de CI; artefactos generados (#293/#294/#295) | Por diseño: esta capacidad conoce la forma de todas las demás lo suficiente para verificarlas (p. ej. `entity-query-lint`, `domain-scope-lint`) |

---

## 5. Direcciones de Dependencia entre Capacidades

Flujo principal del producto (dirección de dependencia, no de tiempo de ejecución — cada flecha es "depende de"):

```
Ingesta ──► Dato Canónico ──► Resolución de Autoridad ──┬─► Enriquecimiento Científico
                                                          └─► Gobernanza/Harmonización
                                                                       │
                                                                       ▼
                                        Analítica/Grafo ◄─── Inteligencia Retrospectiva
                                                │
                                                ▼
                                    Reporte y Artefactos ◄─── Agentic/RAG (opcional)
```

Fundaciones transversales (todo lo anterior depende de estas; ellas no dependen de capacidades de producto):

```
┌─────────────────────────────────────────────────────────────────────┐
│  Auth/RBAC/API Keys  │  Multi-tenancy/Domain Scope  │  Persistencia  │
└─────────────────────────────────────────────────────────────────────┘
```

Substrato de ejecución compartido (capacidades de producto despachan trabajo hacia él; él no conoce lógica de negocio):

```
Cola de Jobs Durable (ADR-007) ◄── encolado por: Reporte, Ingesta (scheduled_imports), Enriquecimiento
```

Contrato externo (se deriva de los routers; nunca al revés):

```
Routers (todas las capacidades) ──► sdk/openapi.json ──► SDK Python/TypeScript ──► Frontend / clientes externos
```

**Regla de dirección permitida:** ninguna capacidad de Grupo A/B debe importar directamente de otra capacidad de negocio salvo a través de su contrato público (función de servicio exportada o endpoint REST); todas pueden depender de Auth/Multi-tenancy/Persistencia; ninguna capacidad de negocio debe ser importada por Auth/Multi-tenancy/Persistencia/Ingeniería de release (la dependencia va en un solo sentido: de negocio hacia plataforma, nunca al revés).

---

## 6. Release Gates y Capacidades Protegidas

Un gate puede proteger varias capacidades; esta tabla no fabrica una relación 1:1. Fuente: `.github/workflows/{test,lint,security,docker,codeql}.yml` en la SHA base de este PR.

| Gate (workflow / job) | Bloqueante | Capacidades que protege |
| --- | --- | --- |
| `test-shard-0..9` (py3.13) — partición determinística #293 (10 shards desde el follow-up de latencia #293, antes 6) | Sí | Prácticamente todas las capacidades de backend con tests (Ingesta, Dato Canónico, Autoridad, Enriquecimiento, Gobernanza, Analítica, Retrospectiva, Reporte, Jobs, Lifecycle, Notificaciones, Workflows, Colaboración, Búsqueda) |
| `test-partition-guard` (unión de shards + cobertura ≥75%) | Sí | Ingeniería de release (garantiza que ningún test se pierde entre shards) |
| `test-py312-compat` (`unit or contract or security`) | Sí | Compatibilidad de runtime de Python para Dato Canónico, Autoridad (tests `contract`), Auth/RBAC (tests `security`) |
| `eval-quality` — Entity-resolution quality gate (F1≥0.75) | Sí | Resolución de Autoridad, Dato Canónico (calidad de dedupe) |
| `postgres-shard-0..5` (migraciones + smoke de arranque + partición del suite completo contra Postgres real, un contenedor Postgres aislado por shard — antes un único job `postgres-smoke` serial, sharded en el follow-up de latencia #293) | Sí | Persistencia (PostgreSQL), CLI/Migraciones (Alembic), y de nuevo la superficie amplia de backend bajo semántica real de Postgres |
| `postgres-partition-guard` (unión de los 6 shards de Postgres == colección exhaustiva, cero solapamiento) | Sí | Ingeniería de release (garantiza que ningún test se pierde entre shards de Postgres) |
| `migration-rehearsal` (pg18) — las 3 migraciones más recientes sobre filas sembradas en todas las tablas, `downgrade`/`upgrade` de la última, y una guarda que rechaza cualquier `UPDATE`/`DELETE`/desactivación de trigger sobre una tabla de solo-añadir aunque no toque ninguna fila (#361; los `postgres-shard` migran sobre una base vacía, donde una migración que reescribe filas no puede fallar) | Sí | CLI/Migraciones (Alembic), Persistencia (PostgreSQL 18, la versión de producción), evidencia de solo-añadir (`backup_assurance_events`) |
| `sdk-smoke` (arranque real + auth + scope-403 + cliente Python/TS) | Sí | SDK y contrato OpenAPI, Auth/RBAC/API Keys, Persistencia (vía migraciones+arranque) |
| `openapi-drift` / `sdk-clients-drift` | Sí | SDK y superficie de contrato OpenAPI |
| `i18n-catalog-gates` + parity | Sí | Shell de frontend (i18n), Reporte (texto server-rendered en PDF/Excel/email usa el mismo catálogo) |
| `domain-scope-lint` | Sí | Multi-tenancy y aislamiento de dominio |
| `entity-query-lint` | Sí | Dato Canónico y CRUD de entidades |
| `backend-lint-changed` + `lint-debt-ratchet` (#294) | Sí | Ingeniería de release (calidad de código de toda capacidad de backend tocada) |
| `frontend-lint` / `frontend-test` / `frontend-typecheck` / `design-system:check` | Sí | Shell de aplicación frontend |
| `frontend-e2e-critical` (Playwright `@critical`) | Sí | Shell de frontend — flujos de producto marcados críticos |
| `repo-metrics-drift` (#295) | Sí | Ingeniería de release (exactitud de métricas/README generados) |
| `enterprise-readiness-lint` | Sí | Enterprise readiness y gobernanza de controles |
| `gitleaks` / `pip-audit` / `npm-audit` | Sí | Ingeniería de release (cadena de suministro); Auth (fuga de secretos) transversalmente |
| `CodeQL` (python, javascript-typescript) | Sí | Ingeniería de release; seguridad transversal a toda capacidad |
| `build-backend` (Trivy + SBOM + **smoke de renderizado real de PDF**) | Sí | Reporte y generación de artefactos (el único gate que ejecuta el runtime de exportación real), Persistencia (runtime Python empaquetado), Ingeniería de release |
| `build-frontend` (Trivy + SBOM) | Sí | Shell de frontend |
| `build-engine` (Trivy + SBOM) | Sí | Motor Rust gRPC |
| `deploy` + verificación post-deploy | Solo en `main` | Ingeniería de release; confirma transversalmente que Auth (`/health`) y Frontend sirven el SHA correcto |

**Sin gate de CI dedicado propio hoy:** Agentic/RAG/NLQ, Integración comercial legacy, Herramientas admin, Demo/Ventas, Cola de jobs durable — consistente con su asignación Tier 3/4 (§3).

### Brechas de protección conocidas (Tier 1/2)

Por la regla de precedencia de §2, ninguna de estas brechas cambia el tier — son objetivos de mejora documentados, no descalificaciones. Se distingue el tipo de brecha porque no todas se cierran de la misma forma.

| Capacidad | Tier | Tipo de brecha | Detalle | Acción propuesta (no implementada aquí) |
| --- | --- | --- | --- | --- |
| Ingesta y adaptadores de origen | 1 | Cobertura de CI | Sin gate bloqueante dedicado — solo suite general (shards) + `postgres-shard`, que no son específicos de ingesta | Candidato a un gate dedicado que verifique invariantes upload→`RawEntity` (p. ej. contract test de ingestión); no implementado en este PR |
| Backup assurance y disaster recovery | 2 | Aseguramiento operacional (no de CI) | `ER-BCP-001`: madurez `specified`, no `operated`; faltan ciclos de backup reales y el primer drill de restore aislado | Ya en el programa de enterprise-readiness (`docs/product/ENTERPRISE_READINESS_PROGRAM.md`, wave ER-2); este PR no acelera ese trabajo, solo lo referencia |

**Caso resuelto por reclasificación, no listado como brecha:** Cola de jobs durable (ADR-007) — en vez de mantenerla Tier 2 con una brecha de "sin cutover verificado", se reclasificó a Tier 3 en §3 porque la evidencia (`docker-compose.prod.yml` sin `UKIP_JOBS_<DOMAIN>`, `ER-OPS-001` en `specified`) muestra que hoy no es una capacidad production-supported en el sentido que Tier 2 exige — es real, gobernada y lista para cutover, pero el cutover mismo aún no ocurrió.

---

## 7. Candidatos a Limpieza de Módulos Acotados (Boundary Debt)

Ningún candidato aquí implica extracción de servicio ni movimiento de código en este PR — es documentación de evidencia y dirección propuesta, tal como exige el contrato de implementación de #296.

### P1 — Integración comercial legacy con nombre engañoso (`backend/adapters/commerce/`, `stores.py`, `StoreConnection`)

**Evidencia:** `backend/adapters/commerce/{woocommerce,shopify,bsale,custom}.py` no tiene ningún importador fuera de su propio paquete (`grep` confirma cero referencias externas). `backend/routers/stores.py` (637 líneas, 16 archivos de test) sí sigue vivo y resuelve el adaptador vía `backend/routers/deps.py::_get_store_adapter`. El modelo `StoreConnection`, sin embargo, se reutilizó como almacén genérico de credenciales de integración externa — lo referencian 14 archivos fuera de `stores.py`, incluyendo `tenant_quotas.py`, `tenant_scoping.py`, `secret_rotation.py`, `data_lifecycle.py` y `ai_rag.py`.

**Dirección propuesta:** documentar explícitamente `stores.py` + `adapters/commerce/` como el módulo acotado "Integración Comercial Legacy" (ya reflejado en la matriz de §3), y evaluar en un PR separado si `backend/adapters/commerce/` en sí (sin `stores.py`, que sigue en uso) puede eliminarse. No renombrar `StoreConnection` en este PR — el modelo tiene 14 consumidores activos y renombrarlo es una migración de datos, fuera de alcance de #296.

### P2 — Resolución de autoridad repartida en tres capas sin mapa único

**Evidencia:** la lógica de "autoridad" vive en `backend/authority/` (motor, 19 módulos), `backend/services/{authority_candidate_extraction,authority_promotion,authority_readiness,institution_authority,institution_reconciliation}.py` (flujos de producto) y 3 routers (`authority.py`, `authority_institutions.py`, `authority_records.py` — los dos últimos con docstring "extracted from authority.py", confirmando un split deliberado que dejó la frontera implícita).

**Dirección propuesta:** el mapa de frontera de §4 ya documenta la separación motor/servicio/router; el siguiente paso natural (no en este PR) es un `README.md` corto dentro de `backend/authority/` que declare explícitamente qué vive en el motor vs. qué vive en `services/authority_*.py`, siguiendo el patrón que `backend/retrospective/` y `backend/jobs/` ya tienen vía sus ADRs dedicados.

### P2 — Gobernanza/harmonización sin paquete dedicado

**Evidencia:** a diferencia de `authority/`, `analyzers/`, `retrospective/` y `jobs/` (cada uno con directorio propio), la capacidad de Gobernanza de Datos/Harmonización no tiene un `backend/governance/` — su lógica está repartida en 3 routers (`harmonization.py`, `transformations.py`, `governance_field_correspondence*.py`, `governance_sources.py`) y 4 servicios sin agrupar.

**Dirección propuesta:** candidato natural para un futuro `backend/governance/` bounded package siguiendo el precedente ya establecido por `authority/`/`analyzers/`/`retrospective/` — no implementado aquí.

### P3 — `backend/analytics/` vs `backend/analyzers/`: colisión de nombres

**Evidencia:** dos paquetes top-level con nombres casi idénticos y propósitos no relacionados — `backend/analytics/` contiene infraestructura RAG/vector (`rag_engine.py`, `vector_store.py`, `montecarlo.py`, usada por 16+ archivos incluyendo `context_engine.py`, routers de RAG/NLQ/ingest/entities), mientras `backend/analyzers/` contiene los 13 analizadores estadísticos (tópicos, correlación, coautoría). Ambos están vivos y en uso — no es código muerto, es riesgo de confusión de import/ownership.

**Dirección propuesta:** renombrar `backend/analytics/` a algo como `backend/rag_infra/` (o fusionar su contenido dentro de la capacidad Agentic/RAG de §3) en un PR de solo-renombrado con actualización mecánica de imports — no ejecutado aquí porque toca ~16 archivos y está fuera del alcance "documentation-first" de #296.

### P3 — Scheduler de staleness de enriquecimiento fuera de la cola durable ADR-007

**Evidencia:** `backend/jobs/handlers.py` registra handlers durables para `report.execute`, `import.execute` y `enrichment.execute` (ADR-007). `backend/services/enrichment_scheduler.py`, en cambio, sigue como loop asyncio propio ("Pure asyncio loop — matches enrichment_worker.py pattern"), fuera de esa cola. Esto es consistente con la migración incremental por dominio que ADR-007 documenta explícitamente (`UKIP_JOBS_<DOMAIN>`) — no es una omisión, es el siguiente dominio candidato natural para migrar.

**Dirección propuesta:** ninguna acción en este PR; queda como el próximo paso documentado de la migración ADR-007 ya en curso. Nota: tras la revisión estratégica de este PR, "Cola de jobs durable (ADR-007)" en sí se reclasificó a Tier 3 (§3) al verificarse que ningún dominio está en modo `queue` en `docker-compose.prod.yml` — este candidato de limpieza describe el siguiente dominio a migrar dentro de ese mismo trabajo en curso, no un problema nuevo.

### P3 — Namespace duplicado `entity_linker.py` (top-level y router)

**Evidencia:** `backend/entity_linker.py` (lógica) y `backend/routers/entity_linker.py` (router) comparten nombre de archivo en namespaces distintos — no es un error funcional (Python los resuelve sin ambigüedad por paquete), pero dificulta la navegación y el grep exploratorio.

**Dirección propuesta:** cuando se toque este archivo por otra razón, considerar un nombre de router más específico (p. ej. `entity_linking_ops.py`), siguiendo la convención ya usada en `governance_field_correspondence_ops.py`/`workspace_reset_ops.py`.

**Prioridad relativa:** P1 (integración comercial) es la más urgente porque afecta directamente cómo se lee la Parte II de este documento — el patrón Adapter/Factory descrito ahí es código real, pero de una capacidad Tier 3 legacy, no de la arquitectura central. P2 son mejoras de mapa de propiedad sin riesgo. P3 son observaciones de bajo riesgo para cuando se toque el código por otra razón.

---

# Parte II — Registro Histórico de Diseño (era DB Disambiguador → UKIP)

> Todo lo que sigue documenta los patrones de diseño y la filosofía de ingeniería adoptados durante la construcción original del sistema (era DB Disambiguador → UKIP temprano). Se conserva porque explica el razonamiento detrás de decisiones que siguen vigentes (p. ej. "no microservicios", "Pydantic como contrato de servicio") y porque parte del código de ejemplo (adaptadores de comercio) sigue en el repositorio como la capacidad Tier 3 "Integración Comercial Legacy" de §3/§7. **No es una descripción del estado actual del sistema** — para eso, ver la Parte I. Las afirmaciones que quedaron objetivamente falsas frente al repositorio actual se corrigieron inline y se marcan con **[Corrección 2026-08]**; el resto se preserva como redactado originalmente.

## 8. Filosofía de Diseño

### El Principio Rector: Complejidad Justificada

> *"La perfección no se alcanza cuando no hay nada más que agregar, sino cuando no hay nada más que quitar."*
> — Antoine de Saint-Exupéry

Este proyecto se rige por una regla fundamental: **cada patrón, cada capa de abstracción y cada decisión arquitectónica debe justificar su existencia resolviendo un problema real y concreto**. No adoptamos patrones porque "es lo que se debe hacer" en la industria, sino porque resuelven un dolor específico que tenemos *hoy* o que tenemos *certeza razonable* de que tendremos mañana.

Este principio sigue gobernando el sistema actual — es la razón por la que §19 (anti-patrones) todavía aplica y por la que #296 explícitamente prohíbe proponer extracción de microservicios sin justificación medida de escala.

### 8.1 — La Curva de la Sobre-Ingeniería

```
Productividad
     ▲
     │            ╱╲
     │           ╱  ╲        ← Zona de Sobre-Ingeniería
     │          ╱    ╲         (más capas, más abstracto,
     │    ●────╱      ╲        pero más lento y frágil)
     │   ╱              ╲
     │  ╱                ╲
     │ ╱                  ╲
     │╱                    ╲
     ├──────────────────────────────► Complejidad Arquitectónica
     │
     Sub-ingeniería  │  Punto   │  Sobre-ingeniería
     (código espagueti)│ Óptimo  │  (astronaut architecture)
```

La sobre-ingeniería es tan dañina como la sub-ingeniería, pero es más insidiosa porque *se siente* productiva. Escribir una interfaz abstracta, tres capas de herencia y un patrón Strategy para algo que podría ser un `if/else` tiene un costo real:

- **Costo cognitivo**: Cada capa de indirección es una capa más que un desarrollador debe comprender.
- **Costo de mantenimiento**: Más archivos, más clases, más tests, más superficie de bugs.
- **Costo de velocidad**: Las abstracciones prematuras congelan decisiones que todavía no entendemos bien.

### 8.2 — Los Tres Filtros de Decisión

Antes de introducir cualquier patrón o abstracción, debe pasar estos tres filtros:

```
┌──────────────────────────────────────────────────────────────┐
│  FILTRO 1: ¿Resuelve un problema que TENEMOS HOY?            │
│  ─────────────────────────────────────────────────            │
│  Si la respuesta es SÍ → Implementar la solución más         │
│  simple que resuelva el problema completo.                    │
│                                                              │
│  Si la respuesta es NO → Pasar al Filtro 2.                  │
├──────────────────────────────────────────────────────────────┤
│  FILTRO 2: ¿El costo de NO implementarlo ahora es alto?      │
│  ─────────────────────────────────────────────────            │
│  ¿Tendría que reescribir código significativo después?        │
│  ¿Violaría un contrato público (API, esquema de BD)?         │
│                                                              │
│  Si SÍ → Implementar la infraestructura mínima.              │
│  Si NO → Pasar al Filtro 3.                                  │
├──────────────────────────────────────────────────────────────┤
│  FILTRO 3: ¿Es gratis o casi gratis?                         │
│  ─────────────────────────────────────                        │
│  ¿Se puede hacer sin agregar complejidad visible?            │
│                                                              │
│  Si SÍ → Hacerlo (ej. nombrar bien una variable).            │
│  Si NO → NO HACERLO. Documentar como decisión futura.        │
└──────────────────────────────────────────────────────────────┘
```

### 8.3 — Ejemplos Concretos de los Filtros en Acción

| Decisión | Filtro | Resultado |
|----------|--------|-----------|
| Usar ORM (SQLAlchemy) en lugar de SQL crudo | Filtro 1 ✅ | Resuelve un problema hoy: 60+ columnas, queries repetitivas, portabilidad de BD. |
| Patrón Adapter para tiendas | Filtro 1 ✅ | Resuelve un problema hoy: 4 APIs distintas con autenticación y formatos diferentes. |
| Usar `BaseStoreAdapter` como ABC | Filtro 2 ✅ | Si no definimos la interfaz ahora, cada adaptador tendría métodos diferentes y el motor de sync no podría ser genérico. |
| NO implementar microservicios | Filtro 1 ❌ | Un solo proceso maneja la carga actual. No hay problema de escala que resolver. |
| NO usar Event Sourcing | Filtro 1 ❌ | El `SyncLog` + `SyncQueueItem` resuelven la auditoría sin la complejidad de reconstruir estado desde eventos. |
| NO usar cache (Redis) | Filtro 1 ❌ | Las queries actuales contra SQLite son sub-milisegundo. No hay problema de rendimiento. |
| Usar diccionario simple para i18n | Filtro 3 ✅ | Con 2 idiomas y ~30 claves, un diccionario TypeScript es literalmente gratis. No agrega complejidad. |
| NO crear un Service Layer separado | Filtro 2 ❌ | La lógica de negocio vive en los endpoints y no se duplica aún. Extraer servicios hoy sería mover código sin ganancia. |

**[Corrección 2026-08]** La fila "NO usar cache (Redis)" describe el estado de 2025. El sistema actual sí usa Redis como cache distribuida opcional (`backend/cache/redis_backend.py`, capacidad "Persistencia y runtimes de datos" en §3) — el trigger de la tabla de §10.1 original ("necesidad de cache por latencia de APIs externas") se cumplió y la decisión se revirtió correctamente, exactamente como el modelo de madurez evolutiva de §10 predice que debía pasar.

### 8.4 — La Regla de las Tres Repeticiones

> **No abstraigas hasta que lo necesites tres veces.**

```
Primera vez:  Escribe la solución directa.
Segunda vez:  Nota la similitud, pero tolera la duplicación.
Tercera vez:  AHORA abstractiza. Ya entiendes el patrón real.
```

Esto aplica a todo: funciones utilitarias, componentes React, endpoints de API. La razón: **la primera y segunda vez no tienes suficiente información para saber qué parte es la que realmente se repite**. Abstraer prematuramente frecuentemente captura las accidentalidades (lo que coincide por casualidad) en lugar de las esencialidades (lo que realmente es un patrón).

**Ejemplo real del proyecto (histórico — este `BaseStoreAdapter` es hoy la capacidad Tier 3 "Integración Comercial Legacy" de §3, no la arquitectura central):**
- Cuando solo teníamos WooCommerce, NO creamos `BaseStoreAdapter`. Lo habríamos diseñado alrededor de las particularidades de WooCommerce.
- Cuando agregamos Shopify (segundo caso), vimos similitudes pero aún no estaba claro el contrato mínimo.
- Al planificar Bsale y Custom (tercero y cuarto), *ya entendemos exactamente qué necesitan todos*: `test_connection()`, `fetch_products()`, `push_product_update()`. La abstracción es precisa porque está basada en experiencia, no en especulación.

---

## 9. Principios SOA Aplicados con Pragmatismo

### ¿Qué nos llevamos de SOA y qué dejamos?

SOA (Service Oriented Architecture) propone principios valiosos. Sin embargo, la implementación clásica de SOA (ESB, WSDL, orquestadores centrales) es un ejemplo perfecto de sobre-ingeniería cuando se aplica a proyectos que no la necesitan. Lo que hacemos es **extraer los principios y aplicarlos al nivel de complejidad que corresponde**.

### 9.1 — Loose Coupling (Débil Acoplamiento) ✅ Adoptado

> *"Los componentes deben saber lo mínimo necesario sobre los demás."*

**En SOA clásico:** Servicios independientes comunicándose vía message bus.
**En nuestro proyecto:** Módulos Python y componentes React que se comunican vía contratos bien definidos.

```
                    Acoplamiento en nuestro sistema

  Frontend ──── HTTP/JSON ────► Backend ──── ORM ────► BD
       │                            │
       │    No sabe que existe      │    No sabe que existe
       │    Python ni el motor de BD│    React ni Next.js
       │                            │
       │    Solo conoce:            │    Solo conoce:
       │    • URLs de endpoints     │    • Modelos SQLAlchemy
       │    • Shapes de JSON        │    • Schemas Pydantic
       ▼                            ▼

  Adapters ──── HTTP ────► APIs Externas
       │
       │    El motor de sync/enriquecimiento
       │    no sabe qué proveedor
       │    es. Solo ve la interfaz
       │    del adaptador base.
       ▼
```

**Dónde lo aplicamos y por qué (ejemplos históricos — la capacidad viva equivalente hoy es "Enriquecimiento científico", §3, con `BaseEnrichmentAdapter` en vez de `BaseStoreAdapter`):**

| Componente | Está acoplado a... | NO está acoplado a... | Beneficio real |
|------------|--------------------|-----------------------|----------------|
| Frontend | Formato JSON de respuestas | Python, SQLAlchemy, lógica de negocio | Se puede reescribir sin tocar backend |
| Endpoints | Schemas Pydantic, ORM | Frontend, estructura de BD física | Cambiar columnas de BD no rompe la API |
| Adapters | Interfaz base del adaptador | Motor que los consume, otros adapters | Agregar proveedor no afecta nada más |
| Motor de sync/enriquecimiento | Objeto normalizado (p. ej. `RemoteProduct` histórico, `attributes_json` hoy) | APIs externas, autenticación específica | La lógica de orquestación es idéntica para todo proveedor |

**Dónde NO lo aplicamos (y por qué) — este razonamiento sigue vigente hoy, ver §19.1 y la capacidad "Ingeniería de release" en §3:**

No separamos el backend en múltiples microservicios porque:
- Un solo proceso sirve todas las rutas. No hay contención de recursos que lo justifique.
- La comunicación interna (función → función) es órdenes de magnitud más rápida que HTTP internos.
- Debugging de un proceso monolítico modular es trivial comparado con debugging distribuido.

### 9.2 — Service Contracts (Contratos de Servicio) ✅ Adoptado

> *"El contrato entre consumidor y proveedor debe ser explícito, estable y versionable."*

**En SOA clásico:** WSDL, XML Schema, contratos formales.
**En nuestro proyecto:** Pydantic schemas + OpenAPI auto-generado — hoy committeado y verificado en CI (`sdk/openapi.json`, gates `openapi-drift`/`sdk-clients-drift`, capacidad "SDK y superficie de contrato OpenAPI" en §3).

```python
# Este schema ES el contrato. Pydantic lo valida, FastAPI lo documenta.
class ExampleCreate(BaseModel):
    name: str                         # Obligatorio
    source: str                       # Obligatorio
    # ...
    api_key: Optional[str] = None     # Opcional, si aplica

class ExampleResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    # Credenciales/campos sensibles EXCLUIDOS del contrato de salida ← decisión de seguridad
```

**¿Por qué no WSDL o GraphQL Schema?**

- WSDL es para ecosistemas SOAP/enterprise. Nosotros usamos REST/JSON.
- GraphQL resuelve el problema de over-fetching/under-fetching que NO tenemos (nuestros endpoints retornan exactamente lo necesario).
- Pydantic schemas hacen lo mismo con menos ceremonia: validación, documentación y tipado automático.

### 9.3 — Service Reusability (Reusabilidad de Servicios) ✅ Adoptado selectivamente

**Lo que SÍ hacemos reutilizable:**
- Los adaptadores: cada implementación puede usarse en cualquier contexto que necesite comunicarse con ese proveedor específico.
- Los schemas: cualquier cliente (no solo nuestro frontend) puede consumir la API porque está documentada vía OpenAPI y distribuida como SDK (Python/TypeScript).
- Las funciones de utilidad: mapeo de columnas, normalización de texto.

**Lo que NO hacemos reutilizable (intencionalmente):**
- Las páginas del frontend. Son específicas de esta aplicación.
- Los endpoints. Están diseñados para los casos de uso de esta app. No pretendemos ser una "plataforma" de propósito genérico ajena a inteligencia de conocimiento.

### 9.4 — Abstraction (Abstracción) ✅ Adoptado con mesura

> *"Un servicio debe ocultar su implementación interna."*

El nivel correcto de abstracción: el frontend no sabe qué patrón interno usa el backend para resolver una request; los endpoints no saben qué proveedor externo específico responde una llamada de enriquecimiento; los adaptadores no saben qué hará el resto del sistema con los datos que normalizan. Cada capa sabe exactamente lo que necesita y **nada más**.

### 9.5 — Composability (Composabilidad) ✅ Adoptado

> *"Los servicios pueden combinarse para crear funcionalidad mayor."*

Cada pieza del pipeline (§5) — ingesta, resolución de autoridad, enriquecimiento, harmonización, analítica, reporte — es independiente y testeable por separado, y se compone hacia el flujo completo del producto.

### 9.6 — Statelessness (Sin estado) ⚠️ Adoptado parcialmente

- **API REST**: Completamente sin estado. Cada request lleva toda la información necesaria (incluyendo el JWT). No hay sesiones de servidor tradicionales.
- **Adaptadores externos**: Sin estado. Se instancian por request y se descartan.
- **Frontend**: Tiene estado local (React state, Context). Esto es deliberado — el estado de UI es inherentemente del cliente.

### 9.7 — Autonomy y Discoverability ⚠️ Adoptados parcialmente

- **Autonomy**: No tenemos servicios independientes desplegados por separado — seguimos siendo un monolito modular bien estructurado (backend Python + engine Rust opcional + frontend Next.js, cada uno con su propio ciclo de build/imagen Docker, pero desplegados como un único sistema coherente). La autonomía completa se vuelve relevante si en el futuro hay evidencia medida de escala u ownership por equipos — ver §19.1, sin cambios respecto al razonamiento original.
- **Discoverability**: El Swagger auto-generado (`/docs`) más el SDK generado y committeado cubren la descubribilidad hoy. Un service registry (Consul, Eureka) seguiría siendo sobre-ingeniería a esta escala.

---

## 10. Modelo de Madurez Evolutiva (histórico)

> **[Corrección 2026-08]** Esta sección describe el plan de evolución tal como se escribió cuando el sistema estaba en su "Fase 1". El sistema **ya no está en Fase 1** — la mayoría de los triggers de §10.1 ya se activaron y las migraciones ya ocurrieron (PostgreSQL en producción, Redis como cache, background jobs vía ADR-007, modularización en 70 routers + 48 servicios). Se conserva como registro de *por qué* se tomaron esas decisiones de evolución, no como el estado actual — para el estado actual, ver Parte I.

### La arquitectura no es estática — evolucionó con el proyecto

En lugar de diseñar para el "caso máximo" desde el día uno, se definieron **puntos de inflexión** claros donde la complejidad se justificaría:

```
    Fase 1 (histórica)        Fase 2 (histórica)         Fase 3 (estado actual, ver Parte I)
    ─────────────             ─────────────               ─────────────
    Monolito simple      →    Monolito modular       →    Monolito modular + servicios opcionales
    SQLite               →    PostgreSQL             →    PostgreSQL + Redis + DuckDB + ChromaDB
    1 archivo main.py    →    main.py + services/    →    70 routers + 48 services + engine Rust opcional
    fetch() directo      →    Client SDK/hooks       →    SDK Python/TypeScript generado desde OpenAPI
    Dict i18n            →    react-i18next-style    →    Catálogo TS proyectado a backend (#269)
    Context API          →    Context API            →    Context API (8 providers) — sigue sin librería externa
```

### 10.1 — Triggers de Evolución (cuándo escalar)

Cada evolución tuvo un **trigger concreto y medible**. No se escaló "por si acaso" — y el registro de qué trigger ya se activó es útil para entender por qué el sistema actual se ve como se ve:

| Trigger | Señal concreta | Acción | Estado |
|---------|----------------|--------|--------|
| `main.py` supera 2000 líneas | Dificultad para navegar, merge conflicts frecuentes | Extraer a `routers/` + `services/` | **Activado** — hoy `main.py` es un orquestador delgado (~160 líneas según `docs/CODEMAPS/backend.md`) y la lógica vive en 70 routers + 48 servicios |
| Más de 5 requests simultáneos causan lentitud | Tiempos de respuesta > 500ms en queries de BD | Migrar de SQLite a PostgreSQL con connection pooling | **Activado** — PostgreSQL es el motor de producción; SQLite se conserva solo para test/local (ver capacidad "Persistencia" en §3) |
| Necesidad de procesamiento en background (syncs largos) | Timeouts en operaciones largas | Incorporar un task queue | **Activado** — cola de jobs durable ADR-007 (§3, §4) |
| Múltiples usuarios concurrentes (> 10) | Conflictos de escritura en SQLite | PostgreSQL + row-level locking | **Activado** |
| Necesidad de cache por latencia de APIs externas | Pulls repetidos a la misma fuente en minutos | Redis como cache de respuestas de adaptadores | **Activado** — `backend/cache/redis_backend.py` |
| Más de 3 idiomas o 100+ claves i18n | El diccionario plano se vuelve difícil de mantener | Adoptar librería i18n completa | **No activado** — EN/ES con proyección generada (#269) sigue siendo suficiente |
| Múltiples equipos trabajan en el proyecto | Merge conflicts diarios en archivos compartidos | Considerar separar frontend y backend en sub-repos | **No activado** — monorepo se mantiene (§13.2) |

### 10.2 — El Principio del Costo Diferido

**La excepción clave:** Si diferir una decisión implica romper un contrato público (schema de BD, API endpoint, formato de exportación), entonces SÍ vale la pena invertir ahora en diseñar la interfaz correcta, incluso si la implementación es simple. Este principio es exactamente el que hoy formalizan los gates de drift de OpenAPI/SDK (§6) — el contrato público no puede romperse en silencio.

---

## 11. Arquitectura Cliente-Servidor (histórico)

> **[Corrección 2026-08]** El diagrama original mostraba únicamente SQLite y el puerto de desarrollo local. El estado actual (múltiples motores de persistencia, PostgreSQL en producción) está en la capacidad "Persistencia y runtimes de datos" de §3. El razonamiento de *por qué* separar frontend/backend sigue siendo válido y se conserva íntegro abajo.

```
┌──────────────────┐         HTTP/JSON         ┌──────────────────┐
│                  │  ◄──────────────────────►  │                  │
│   Frontend       │                            │   Backend        │
│   (Next.js)      │    GET, POST, PUT, DELETE  │   (FastAPI)      │
│                  │                            │                  │
└──────────────────┘                            └────────┬─────────┘
                                                         │
                                                         ▼
                                                ┌──────────────────┐
                                                │ PostgreSQL (prod)│
                                                │ SQLite (test/dev)│
                                                └──────────────────┘
```

**¿Por qué y no un monolito full-stack (como Django templates)?**

- **Separación de responsabilidades**: El frontend se encarga exclusivamente de la presentación y la interacción del usuario. El backend maneja la lógica de negocio, validación y persistencia. Esto permite que ambos evolucionen independientemente.
- **Flexibilidad de despliegue**: Se pueden escalar, desplegar o reemplazar de forma independiente. El backend podría ser consumido por otros clientes (apps móviles, scripts CLI, el SDK generado) sin cambios — esto ya ocurre hoy vía `sdk/`.
- **Contratos claros**: La comunicación se realiza exclusivamente vía API REST con JSON, creando un contrato bien definido entre las capas.
- **¿No es esto sobre-ingeniería?** No, porque la separación es esencialmente "gratis" con FastAPI + Next.js, y resuelve un problema real: poder iterar en la UI sin riesgo de romper la lógica de datos.

---

## 12. Patrones de Diseño (histórico)

### 12.1 — Repository Pattern (implícito vía SQLAlchemy ORM)

**Archivo:** `backend/models.py`, `backend/database.py`

```python
# database.py — Sesión centralizada
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# En endpoints:
def get_products(db: Session = Depends(get_db)):
    return db.query(models.RawProduct).all()
```

**¿Por qué?**

- **Abstracción del almacenamiento**: Los endpoints no necesitan saber si los datos vienen de SQLite, PostgreSQL o cualquier otro motor. Solo interactúan con objetos Python.
- **Gestión automática del ciclo de vida**: El patrón `yield` con `Depends()` asegura que cada request obtiene su propia sesión de BD, y que se cierra correctamente al finalizar — evitando fugas de conexiones.
- **Portabilidad**: Cambiar de SQLite a PostgreSQL requiere solo modificar `SQLALCHEMY_DATABASE_URL`. Los modelos y queries no cambian — esto es exactamente lo que ya ocurrió (§10.1).

**¿Por qué NO un Repository explícito (clase `ProductRepository`)?**

Porque el `Session` de SQLAlchemy YA es un repository. Crear una clase wrapper solo agregaría una capa de indirección sin funcionalidad nueva. Cuando queries complejas se repiten en múltiples endpoints (trigger: 3 repeticiones), se extraen funciones de consulta — no antes. `entity_base_q` (§3, "Dato canónico") es exactamente ese caso ya ejecutado.

---

### 12.2 — Data Transfer Object (DTO) / Schema Validation con Pydantic

**Archivo:** `backend/schemas.py`

**¿Por qué?**

- **Validación automática**: FastAPI valida cada request contra el schema antes de ejecutar la lógica. Un campo faltante o de tipo incorrecto se rechaza con un error 422 antes de llegar al código.
- **Seguridad por diseño**: Los schemas de respuesta excluyen deliberadamente campos sensibles (credenciales, llaves de API). Esto hace imposible que credenciales se filtren accidentalmente al frontend.
- **Documentación viva**: Los schemas generan automáticamente la documentación OpenAPI (Swagger) en `/docs`, creando un contrato API siempre actualizado — y hoy también el SDK generado.
- **Separación de concerns**: Un modelo ORM difiere del input esperado (`*Create`) y de la respuesta enviada (`*Response`). Esto permite que la BD tenga campos que nunca se exponen.

---

### 12.3 — Adapter Pattern (histórico — el ejemplo original es la capacidad Tier 3 "Integración Comercial Legacy")

**Directorio (código real, aún en el repositorio):** `backend/adapters/commerce/`

```python
# base.py — Interfaz abstracta
class BaseStoreAdapter(ABC):
    @abstractmethod
    def test_connection(self) -> ConnectionTestResult: ...
    @abstractmethod
    def fetch_products(self, page, per_page) -> List[RemoteProduct]: ...
    @abstractmethod
    def push_product_update(self, remote_id, updates) -> bool: ...

# woocommerce.py — Implementación concreta
class WooCommerceAdapter(BaseStoreAdapter):
    def fetch_products(self, page=1, per_page=50):
        resp = self._request("GET", "products", params={...})
        return [self._parse_product(p) for p in resp.json()]

# __init__.py — Factory
def get_adapter(platform: str, config: dict) -> BaseStoreAdapter:
    adapters = {
        "woocommerce": WooCommerceAdapter,
        "shopify": ShopifyAdapter,
        "bsale": BsaleAdapter,
        "custom": CustomAPIAdapter,
    }
    return adapters[platform](config)
```

**El mismo patrón, vivo hoy en la capacidad central "Enriquecimiento científico" (§3):** `backend/adapters/enrichment/base.py` define la interfaz que `openalex.py`, `crossref.py`, `pubmed.py`, `wos.py`, `scopus.py`, `semantic_scholar.py`, `dblp.py`, `doaj.py` y `scholar.py` implementan, con el mismo razonamiento de Open/Closed y polimorfismo que se explica abajo. El ejemplo de comercio se conserva porque es el original que motivó la decisión.

**¿Por qué?**

- **Principio Abierto/Cerrado (OCP)**: Agregar un nuevo proveedor requiere solo crear una nueva clase que herede de la interfaz base. No se modifica ningún código existente.
- **Polimorfismo**: El motor consumidor no sabe (ni necesita saber) con qué proveedor específico está interactuando.
- **Testabilidad**: Se puede crear un adaptador mock para pruebas sin necesidad de conectarse a APIs reales.
- **Complejidad encapsulada**: Cada proveedor tiene su propia autenticación, formatos de datos y paginación, encapsulados dentro de cada adaptador.

**¿Es esto sobre-ingeniería?** No. Éste es un caso donde la abstracción existe porque hay múltiples implementaciones reales con diferencias significativas. Sin ella, tendríamos condicionales `if provider == "..."` dispersos por todo el código.

---

### 12.4 — Factory Pattern (histórico, mismo patrón vivo en enriquecimiento)

**Archivo:** `backend/adapters/__init__.py` (comercio, histórico); patrón equivalente en `backend/adapters/enrichment/`

```python
def get_adapter(platform: str, config: dict) -> BaseStoreAdapter:
    adapters = {
        "woocommerce": WooCommerceAdapter,
        "shopify": ShopifyAdapter,
        "bsale": BsaleAdapter,
        "custom": CustomAPIAdapter,
    }
    adapter_class = adapters.get(platform)
    if not adapter_class:
        raise ValueError(f"Unsupported platform: {platform}")
    return adapter_class(config)
```

**¿Por qué?**

- **Desacoplamiento**: El código consumidor no importa ni instancia directamente las clases de adaptadores.
- **Punto único de registro**: Agregar un nuevo adaptador requiere solo registrarlo en el diccionario. Es un cambio de una línea.
- **Inversión de dependencia (DIP)**: Los consumidores dependen de la abstracción, no de implementaciones concretas.

---

### 12.5 — Normalized Data Object Pattern

**Archivo (histórico):** `backend/adapters/base.py` — el equivalente vivo hoy es `attributes_json` en `RawEntity`, poblado de forma normalizada por cada adaptador de enriquecimiento.

**¿Por qué?**

- **Normalización de datos heterogéneos**: cada proveedor externo nombra y estructura sus campos de forma distinta; el objeto normalizado unifica todo en un formato estándar.
- **Preservación del dato original**: guardar el payload original permite auditoría, debugging, y acceso a campos que quizás no se mapearon inicialmente.

---

## 13. Patrones Estructurales (histórico)

### 13.1 — Layered Architecture (Arquitectura en Capas)

```
┌───────────────────────────────────────────────────┐
│                  Presentación                      │  ← Frontend (React/Next.js)
├───────────────────────────────────────────────────┤
│                  API / Controlador                 │  ← FastAPI routers (backend/routers/)
├───────────────────────────────────────────────────┤
│                  Lógica de Negocio                 │  ← backend/services/, backend/authority/, adapters
├───────────────────────────────────────────────────┤
│                  Acceso a Datos                    │  ← SQLAlchemy ORM (models.py)
├───────────────────────────────────────────────────┤
│                  Persistencia                      │  ← PostgreSQL (prod) / SQLite (test)
└───────────────────────────────────────────────────┘
```

**[Corrección 2026-08]** El texto original notaba honestamente que "API/Controlador" y "Lógica de Negocio" vivían juntas en `main.py`. Eso ya no es así: la separación entre `routers/` (controlador) y `services/`/`authority/`/`adapters/` (lógica de negocio) es real y es precisamente el resultado del trigger de evolución de §10.1 ("`main.py` supera 2000 líneas").

---

### 13.2 — Monorepo Structure

```
universal-knowledge-intelligence-platform/
├── backend/       ← Módulo Python independiente
├── frontend/      ← Módulo Node.js independiente
├── engine/        ← Módulo Rust independiente (opcional)
├── sdk/           ← Clientes generados
├── docs/          ← Documentación compartida
└── scripts/       ← Utilidades transversales
```

**¿Por qué?**

- **Cohesión del proyecto**: Todo el código vive en un solo repositorio, facilitando los PRs que involucran cambios full-stack.
- **Versionado atómico**: Un commit puede incluir cambios coordinados en backend y frontend, evitando desincronización.
- **Simplicidad operativa**: Un solo `git clone` obtiene todo lo necesario para ejecutar la aplicación.

Esta decisión no ha cambiado desde el diseño original y sigue siendo correcta a la escala actual — ver §19.1.

---

## 14. Patrones de Integración (histórico, sync de tiendas)

> Esta sección completa describe el flujo de sincronización de tiendas e-commerce original. El código sigue existiendo (capacidad Tier 3 "Integración Comercial Legacy", §3/§7) pero **no describe cómo fluye el dato en el producto actual** — para eso, ver §5 (direcciones de dependencia entre capacidades del pipeline actual: ingesta → dato canónico → autoridad → enriquecimiento → gobernanza/analítica → reporte).

### 14.1 — Human-in-the-Loop (Supervisión Humana)

```
    Pull de         Cola de            Revisión         Aplicación
    Tienda   ──►   Pendientes   ──►   Humana    ──►   de Cambios
                  (SyncQueueItem)     (Approve/        (status: applied)
                                       Reject)
```

**¿Por qué?**

- **Control de calidad**: Los datos de tiendas externas pueden contener errores, duplicados o formatos inconsistentes. Un humano revisa antes de integrar.
- **Reversibilidad**: Si un cambio se aprueba por error, existe un registro claro de quién aprobó qué y cuándo.
- **Auditoría**: Cada acción queda registrada, creando un trail completo de todas las operaciones de sincronización.

El principio de human-in-the-loop sigue vivo en el producto actual bajo otras formas — p. ej. la resolución de autoridad (§3) tiene endpoints explícitos de confirm/reject, y la cola de jobs durable (ADR-007) tiene replay autorizado en vez de automático.

### 14.2 — Canonical URL Mapping (Mapeo por URL Canónica)

Mapeo histórico específico del dominio de comercio (URL de producto como identificador estable entre sistemas). El equivalente actual para entidades científicas es la resolución de autoridad contra fuentes externas (OpenAlex ID, DOI, ORCID, ROR) — un problema estructuralmente similar (identidad estable entre sistemas) resuelto por una capacidad completamente distinta (§3, "Resolución de autoridad e identidad").

### 14.3 — Change Detection Pattern (Detección de Cambios)

```python
# En el pull, se comparan campos críticos:
if existing.remote_name != rp.name:
    changes.append(("name", existing.remote_name, rp.name))
```

**¿Por qué?** Eficiencia (solo se registran cambios reales), granularidad (cada campo se aprueba/rechaza independientemente), idempotencia (múltiples pulls no duplican).

---

## 15. Patrones de Frontend

### 15.1 — File-Based Routing (Next.js App Router)

```
frontend/app/
├── page.tsx              → /
├── analytics/page.tsx    → /analytics
├── entities/
│   ├── page.tsx          → /entities
│   └── [id]/page.tsx     → /entities/:id  (ruta dinámica)
└── ...  (~28 superficies de producto, ver §1)
```

Sigue siendo el patrón actual — la lista de ejemplo se actualizó (§1) para reflejar las superficies reales de hoy en vez del catálogo de e-commerce original.

**¿Por qué?**

- **Convención sobre configuración**: La estructura del filesystem define las rutas.
- **Colocación**: Cada ruta tiene su código en su propia carpeta.
- **Code splitting automático**: Next.js solo carga el JavaScript necesario para cada página.

### 15.2 — Context Pattern para Estado Global

**Archivos actuales:** `frontend/app/contexts/{AssistantContext,AuthContext,BrandingContext,DomainContext,EnrichmentContext,LanguageContext,PilotModeContext,ThemeContext}.tsx` (8 providers, coincide con el conteo de §1).

**¿Por qué?**

- **Prop drilling prevention**: sin Context, habría que pasar estado a través de muchos niveles de componentes.
- **Single source of truth**: cada dominio de estado global vive en un solo lugar.
- **Escalabilidad controlada**: para estado más complejo, se podría migrar a Zustand o TanStack Query sin cambiar la API de consumo — no ha sido necesario.

**¿Por qué no Zustand o Redux desde el inicio?** 8 contexts bien delimitados siguen sin justificar una librería de state management adicional bajo el Filtro 3 (§8.2).

### 15.3 — Patrón de Componentes Presentacionales

`frontend/app/components/` tiene hoy 55+ componentes top-level. El razonamiento original se mantiene: reutilización, encapsulamiento, facilidad de testing.

---

## 16. Patrones de Datos

### 16.1 — Column Mapping (Mapeo de Columnas)

**Histórico:** vivía en `main.py` con ~60 mapeos hardcodeados para el catálogo Excel de e-commerce. **Estado actual:** la capacidad "Ingesta y adaptadores de origen" (§3) tiene un router dedicado, `backend/routers/column_maps.py`, con mapeo universal de headers → nombres de campo para import/export — el mismo principio, generalizado más allá de un solo dominio.

**¿Por qué?**

- **Desacoplamiento de formato externo e interno**: los archivos fuente pueden tener headers en cualquier idioma/convención; internamente se usa un formato consistente.
- **Punto único de verdad**: si un nombre de columna cambia en la fuente, solo hay que actualizar un mapeo.

### 16.2 — Harmonization Pipeline con Undo/Redo

```
Paso 1: Normalizar        Paso 2: Corregir        Paso 3: Estandarizar
valores en minúsculas →  typos con Levenshtein  →  formatos
        │                        │                        │
        └─── Log + Changes ──── └─── Log + Changes ──── └─── Log + Changes
                                    (cada paso reversible)
```

Vivo hoy en la capacidad "Gobernanza de datos, harmonización y transformación" (§3), `backend/routers/harmonization.py` (`/harmonization/apply`, `/undo`, `/redo`).

**¿Por qué?** Trazabilidad completa, reversibilidad, independencia de pasos.

### 16.3 — Internationalization (i18n) por Diccionario Proyectado

**Archivo:** `frontend/app/i18n/translations.ts`, proyectado a `backend/i18n/catalog.*.json` (issue #269, gates `i18n-catalog-gates`/parity en §6).

**¿Por qué?**

- **Simplicidad**: para 2 idiomas, un diccionario TypeScript sigue siendo más ligero que una librería completa.
- **Type safety**: TypeScript verifica que las claves existen en ambos idiomas en tiempo de compilación.
- **Fuente única, proyección generada**: el backend nunca mantiene su propia copia manual — la proyección se regenera y se verifica en CI, exactamente el mismo principio que #295 aplica a las métricas del README.

---

## 17. Decisiones Técnicas Clave (histórico, con corrección)

### ¿Por qué FastAPI (y no Django, Flask, Express)?

| Criterio | FastAPI | Django | Flask |
|----------|---------|--------|-------|
| Validación automática | ✅ Pydantic nativo | ⚠️ Requiere DRF | ❌ Manual |
| Documentación API | ✅ Swagger auto | ⚠️ Con DRF | ❌ Plugin |
| Performance | ✅ ASGI async-ready | ⚠️ WSGI | ⚠️ WSGI |
| Curva de aprendizaje | ✅ Mínima | ⚠️ Mayor (ORM propio) | ✅ Mínima |
| Ecosistema Python | ✅ Compatible total | ✅ Extenso | ✅ Compatible |

**Decisión**: FastAPI ofrece el mejor balance entre productividad, validación y documentación automática para una API REST de gestión de datos. Esta decisión no ha cambiado.

### ¿Por qué PostgreSQL en producción (y SQLite solo para test/local)?

> **[Corrección 2026-08]** Esta sub-sección originalmente argumentaba a favor de SQLite como motor de producción ("Fase actual: herramienta local/mono-usuario"). Esa afirmación es hoy **falsa**: `Dockerfile.backend` y los `postgres-shard` de CI (§6) confirman que PostgreSQL es el motor de producción; SQLite se usa únicamente para tests y desarrollo local (`DATABASE_URL=sqlite:///:memory:` en los shards de CI). El razonamiento original de portabilidad del ORM sigue siendo la razón por la que la migración fue posible sin reescribir queries — eso se conserva:

- **Portabilidad vía ORM**: SQLAlchemy abstrae el motor. La migración de SQLite a PostgreSQL requirió cambiar la URL de conexión y agregar Alembic para las migraciones de schema, sin reescribir la lógica de queries.
- **Por qué SQLite igual se conserva para test/local**: es un archivo, no requiere levantar un servidor, y las suites de test corren más rápido en memoria — trade-off documentado en la capacidad "Persistencia y runtimes de datos" (§3).

### ¿Por qué Next.js (y no Vite + React, Angular)?

- **App Router**: Routing declarativo por filesystem, sin configuración.
- **SSR/SSG**: Capacidad de renderizado del lado del servidor.
- **Full-stack ready**: soporta API routes internas o middleware si se necesitan.

---

## 18. Diagrama de Flujo de Datos (histórico, sync de tiendas)

> Este diagrama describe el flujo de sincronización de tiendas e-commerce original. **Para el flujo de datos del producto actual, ver §5** (Ingesta → Dato Canónico → Autoridad → Enriquecimiento → Gobernanza/Analítica → Reporte).

```
                           ┌─────────────────────┐
                           │   Tienda Virtual     │
                           │  (WooCommerce,       │
                           │   Shopify, Bsale)    │
                           └──────────┬──────────┘
                                      │
                              API REST (fetch)
                                      │
                                      ▼
                           ┌─────────────────────┐
                           │   Adapter Layer      │
                           └──────────┬──────────┘
                                      │
                             Objeto normalizado
                                      │
                                      ▼
                    ┌──────────────────────────────────┐
                    │      Canonical URL Matching       │
                    └──────┬───────────────┬────────────┘
                           │               │
                      NO (nuevo)      SÍ (existente)
                           │               │
                           ▼               ▼
                  ┌──────────────┐  ┌──────────────────┐
                  │ Crear Mapping │  │ Detectar Cambios  │
                  │ + Queue Item  │  │ → Queue Items      │
                  └──────┬───────┘  └────────┬───────────┘
                         │                   │
                         └─────────┬─────────┘
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │   Cola de Revisión   │
                        │   status: "pending"  │
                        └──────────┬──────────┘
                                   │
                           Revisión humana
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │   SyncLog            │
                        └─────────────────────┘
```

---

## 19. Anti-Patrones: Lo Que Decidimos NO Hacer

Tan importante como documentar lo que hacemos es documentar lo que **decidimos no hacer** y por qué. Estas decisiones son activas, no omisiones accidentales — y siguen vigentes hoy (issue #296 explícitamente prohíbe proponer extracción de microservicios sin justificación medida).

### 19.1 — NO microservicios

**¿Por qué?** Los microservicios resuelven problemas de *escala organizacional* (múltiples equipos, despliegue independiente) o de *aislamiento de fallo/escala diferencial* medido. UKIP hoy es un monolito modular (70 routers, 48 servicios, paquetes acotados como `authority/`, `analyzers/`, `retrospective/`, `jobs/`) con un componente Rust opcional (`engine/`) ya desplegado como imagen separada — es decir, **ya existe separación de despliegue donde hay evidencia real de carga diferencial** (el motor de grafos/texto), sin haber pagado el costo de descomponer todo el sistema.

**Cuándo reconsiderar (sin cambios respecto al razonamiento original):** cuando haya evidencia medida de que un módulo específico necesita escalar independientemente del resto, o cuando múltiples equipos tengan conflictos de ownership frecuentes sobre las mismas partes del código — ninguna de las dos condiciones tiene evidencia en el repositorio hoy.

### 19.2 — NO Event Sourcing / CQRS (con matiz)

**¿Por qué no, en general?** El estado actual vive en las tablas directamente; los logs de auditoría (`audit_log`, `AuthorityRecord` con estado, historial de harmonización) proveen trazabilidad sin la complejidad de reconstrucción de estado.

**Matiz 2026-08:** la capacidad "Inteligencia retrospectiva" (§3, ADR-006) *sí* implementa un patrón de eventos append-only — pero deliberadamente acotado a un bounded context específico (reconstrucción punto-en-el-tiempo para análisis histórico), no como arquitectura general de persistencia. Esto es exactamente el patrón de "Filtro 2" (§8.2): se pagó el costo donde había un problema real y concreto (necesidad de comparar snapshots en el tiempo), no en general.

### 19.3 — NO GraphQL

**¿Por qué no?** GraphQL brilla cuando el frontend necesita combinaciones flexibles de datos, hay over-fetching severo, o múltiples clientes consumen la API de formas distintas. El sistema actual sirve un frontend propio más un SDK generado (Python/TypeScript) desde el mismo contrato OpenAPI — no hay evidencia de que REST+SDK generado esté limitando a ningún consumidor.

### 19.4 — NO Message Queue de propósito general (RabbitMQ, Kafka)

**[Corrección 2026-08]** El trigger original ("si un pull de 1000+ productos tarda > 60 segundos y necesita ejecutarse en background") **ya se activó**, pero la solución elegida fue una cola de jobs durable propia sobre PostgreSQL (ADR-007, §3) en vez de adoptar un message broker de propósito general — decisión documentada explícitamente en el ADR: evita una pieza de infraestructura adicional para un volumen de trabajo que no la justifica.

### 19.5 — NO Container Orchestration (Kubernetes) de propósito general

Docker Compose (vía Dokploy) sigue siendo suficiente: 3 imágenes (backend, frontend, engine) desplegadas juntas, sin necesidad de auto-scaling o despliegues zero-downtime multi-instancia hoy.

---

## 20. Guía de Decisión para Nuevas Features

Antes de implementar cualquier feature nueva, hazte estas preguntas:

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  1. ¿CUÁL ES EL PROBLEMA?                                       │
│     Describe el problema en una oración sin mencionar            │
│     la solución. Si no puedes, quizás no hay problema.           │
│                                                                  │
│  2. ¿CUÁL ES LA SOLUCIÓN MÁS SIMPLE?                            │
│     ¿Se puede resolver con una función? ¿Un campo en la BD?     │
│     ¿Un componente? Empieza por ahí.                             │
│                                                                  │
│  3. ¿QUÉ CONTRATO ESTABLEZCO?                                   │
│     ¿Estoy creando un endpoint público? ¿Un schema de BD?       │
│     ¿Una prop de componente? Estos contratos son difíciles       │
│     de cambiar — diseñarlos bien SÍ vale la inversión.           │
│                                                                  │
│  4. ¿A QUÉ CAPACIDAD PERTENECE? (nuevo, post-#296)              │
│     ¿Encaja dentro de la frontera de una capacidad existente    │
│     (§3/§4), o define una nueva? Si es nueva, ¿qué tier?        │
│                                                                  │
│  5. ¿QUÉ PRECEDENTE CREO?                                       │
│     Si lo hago así, ¿el equipo seguirá este patrón?             │
│                                                                  │
│  6. ¿PUEDO BORRARLO FÁCILMENTE?                                 │
│     El mejor código es el que se puede eliminar sin              │
│     efectos colaterales. Si tu abstracción no se puede           │
│     borrar limpiamente, es demasiado acoplada.                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 21. Principios SOLID Aplicados

| Principio | Implementación | Nota pragmática |
|-----------|----------------|-----------------|
| **S** – Single Responsibility | Cada adaptador maneja solo su proveedor. Cada componente React maneja solo su UI. Cada router de `backend/routers/` cubre un área acotada. | La disciplina de mantener routers/servicios pequeños es hoy verificada indirectamente por `entity-query-lint`/`domain-scope-lint` sobre los archivos que sí tocan esos contratos. |
| **O** – Open/Closed | Nuevos proveedores (enriquecimiento, LLM) se agregan creando nuevas clases, sin modificar las existentes. | Aplicado donde hay variabilidad real (adapters). No aplicado donde no la hay. |
| **L** – Liskov Substitution | Cualquier adaptador de un proveedor puede sustituir a otro donde se espere la interfaz base. | Verificado por tests de contrato (`test_enrichment_adapter_contract.py`). |
| **I** – Interface Segregation | Las interfaces base definen solo los métodos que TODAS las implementaciones necesitan. | Si una implementación necesita un método especial, va en la subclase — no en la interfaz base. |
| **D** – Dependency Inversion | Los routers dependen de interfaces de adaptador/servicio (abstracción), no de implementaciones concretas. | Implementado vía Factory/registro. |

---

## 22. Resumen Ejecutivo (histórico)

```
┌────────────────────────────────────────────────────────────────┐
│                  NUESTRO EQUILIBRIO (razonamiento original,     │
│                  sigue vigente — ver Parte I para el estado)    │
│                                                                │
│   ✅ Débil acoplamiento              — SÍ, entre módulos      │
│   ✅ Fuerte interoperabilidad        — SÍ, vía REST/JSON      │
│   ✅ Contratos de servicio           — SÍ, vía Pydantic +      │
│                                         OpenAPI + SDK generado │
│   ✅ Abstracción donde hay variación — SÍ, Adapter Pattern    │
│   ✅ Auditoría y trazabilidad        — SÍ, audit log + ADR-006│
│                                                                │
│   ❌ Microservicios                  — NO, sin evidencia      │
│                                         medida de escala       │
│   ❌ Event Bus / CQRS general        — NO (acotado a          │
│                                         retrospectiva, ADR-006)│
│   ❌ GraphQL                         — NO, resuelve problemas │
│                                         que no tenemos         │
│   ❌ Container orchestration general — NO, escala insuficiente│
│                                                                │
│   Filosofía: Cada patrón justifica su existencia.              │
│   Si no resuelve un problema real, no se implementa.           │
│   Si luego lo necesitamos, lo implementaremos — con datos.     │
│   Ver Parte I §2 para los niveles de soporte operacionales     │
│   que hoy formalizan esta misma disciplina por capacidad.      │
└────────────────────────────────────────────────────────────────┘
```

---

*Este documento se actualiza conforme evoluciona la arquitectura del proyecto. Cada actualización debe incluir el trigger que motivó el cambio. La Parte I (capacidades, tiers, fronteras, release gates) es el artefacto canónico de arquitectura vigente — actualícela primero ante cualquier cambio real de capacidad o frontera. La Parte II es registro histórico y solo debe tocarse para corregir una afirmación que se volvió falsa.*
