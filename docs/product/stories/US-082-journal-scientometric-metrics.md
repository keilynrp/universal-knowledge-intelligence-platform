# US-082 - Journal scientometric metrics (NIF, NIF Bayes, APC) as open proxies

## 1. User story

Como investigador, quiero ver métricas de revista (factor de impacto normalizado y su versión bayesiana, APC, acceso abierto) junto a cada publicación, para evaluar el contexto de publicación con indicadores abiertos y honestos sobre su incertidumbre.

## 2. Context

UKIP no exponía métricas a nivel de revista. Se añadió un frente cienciométrico sobre OpenAlex, con el encuadre explícito de "open proxy" (no JIF de Clarivate).

- Epic: `EPIC-004`
- Sprint objetivo: `SPRINT-105`

## 3. Acceptance criteria

- [x] NIF (open proxy) calculado y normalizado por campo (`normalized_impact_factor`, `nif_field`)
- [x] NIF Bayes (Empirical-Bayes Gamma-Poisson) con intervalo de credibilidad 95% (`nif_bayes`, `nif_ci_low`, `nif_ci_high`), mostrado junto al NIF sin reemplazarlo
- [x] APC, DOAJ y works count capturados desde OpenAlex/DOAJ
- [x] Surfaces: dashboard `/analytics/journals`, modal de entidad, y ficha de detalle `/entities/[id]`
- [x] Backfill idempotente y trazabilidad actualizada

## 4. Functional notes

- Todo etiquetado como "open proxy" en la UI.
- NIF Bayes encoge revistas con muestra pequeña/ruidosa hacia la media del campo.
- Disparador de UI: la entidad tiene `issn_l` (artículos/reviews en revista).

## 5. Technical notes

- modulos: `backend/analyzers/journal_normalization.py`, `backend/analyzers/journal_normalization_bayes.py`, `backend/routers/journals.py`, `backend/services/journal_metrics_service.py`, `backend/schemas.py`
- frontend: `frontend/app/analytics/journals/`, `JournalMetricsSection.tsx`, `EntityTableDetailsModal.tsx`, `entities/[id]/page.tsx`
- backfill: `backend/scripts/backfill_nif_bayes.py` (ver `docs/operating/BACKFILL_RUNBOOK.md`)
- PRs: #77, #82, #83 (NIF/APC/works), #90, #91 (NIF Bayes), #97 (detail page)

## 6. Definition of done

- [x] implementado
- [x] probado
- [x] documentado
- [x] trazabilidad actualizada

## 7. Evidence

- Specs/plans: `docs/superpowers/specs/2026-06-25-journal-nif-bayesian-design.md`, `docs/superpowers/specs/2026-06-26-nif-bayes-frontend-surfacing-design.md`
- Domain doc: `docs/SCIENTOMETRICS.md` (§1.b Indicadores implementados)
- Epic: `docs/product/epics/EPIC-004-authority-and-enrichment.md`
