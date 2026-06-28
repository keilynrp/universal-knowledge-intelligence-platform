# US-083 - Work-type classification and filterable facet (OpenAlex work.type)

## 1. User story

Como analista, quiero filtrar y ver el tipo de obra de cada entidad (artículo, libro, tesis, preprint, dataset…) para segmentar el catálogo por la clasificación autoritativa de OpenAlex.

## 2. Context

`entity_type` era un hint grueso de ingest. OpenAlex provee `work.type` (vocabulario controlado), que no se capturaba. Se añadió como dimensión propia.

- Epic: `EPIC-004`
- Sprint objetivo: `SPRINT-105`

## 3. Acceptance criteria

- [x] `work.type` capturado en enriquecimiento (`enrichment_work_type`) + migración + expuesto en el API de entidad
- [x] Mapeo raw→categoría (un solo origen de verdad backend + espejo frontend)
- [x] Facet `work_type` en el panel lateral con filtro `ft_work_type` (NULLs → "Sin clasificar")
- [x] Badges de tipo en tabla, modal y ficha de detalle
- [x] Backfill idempotente y trazabilidad actualizada

## 4. Functional notes

- Categorías: Article / Book / Thesis / Preprint / Dataset / Other / Unclassified.
- Facet aditivo; no altera la semántica del `entity_type` existente.

## 5. Technical notes

- modulos: `backend/services/work_type.py`, `backend/adapters/enrichment/openalex.py`, `backend/enrichment_worker.py`, `backend/models.py`, `backend/services/entity_service.py`, `backend/routers/entities.py`
- frontend: `frontend/app/lib/workType.ts`, `FacetPanel.tsx`, `EntityTableContent.tsx`, `EntityTableDetailsModal.tsx`, `entities/[id]/page.tsx`
- backfill: `backend/scripts/backfill_work_type.py` (ver `docs/operating/BACKFILL_RUNBOOK.md`)
- PRs: #93 (facet/filter), #94 (modal+table badges), #96 (detail-page row)

## 6. Definition of done

- [x] implementado
- [x] probado
- [x] documentado
- [x] trazabilidad actualizada

## 7. Evidence

- Spec/plan: `docs/superpowers/specs/2026-06-26-openalex-work-type-facet-design.md`, `docs/superpowers/plans/2026-06-26-openalex-work-type-facet.md`
- Epic: `docs/product/epics/EPIC-004-authority-and-enrichment.md`
