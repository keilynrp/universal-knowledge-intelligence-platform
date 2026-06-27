# Changelog

All notable changes to the **UKIP (Universal Knowledge Intelligence Platform)** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project aims to adhere to Semantic Versioning where possible.

## [Unreleased]

### Added
- **Journal NIF + APC enrichment:** OpenAlex journal-level metrics captured per entity — Normalized Impact Factor (**NIF**, an open-proxy of 2-year mean citedness, field-normalized — explicitly **not** a Clarivate JIF), APC (article processing charge), DOAJ open-access flag, and per-journal works count. Surfaced in the entity-detail "Journal" section and the `/analytics/journals` ranking dashboard (sortable table + charts + admin recompute). (PRs #77, #82, #83)
- **Bayesian NIF (`nif_bayes`):** Uncertainty-aware companion to NIF using closed-form Empirical-Bayes Gamma-Poisson shrinkage toward the field mean, with a 95% credible interval (`nif_ci_low`/`nif_ci_high`). Shown alongside NIF (never replacing it) in the modal card and as a sortable, NULLs-last column in the journals ranking table. Optional backfill: `backend/scripts/backfill_nif_bayes.py`. (PRs #90, #91)
- **Work-type facet (OpenAlex `work.type`):** Captured into `enrichment_work_type` and exposed as a grouped sidebar facet (Article / Book / Thesis / Preprint / Dataset / Other / Unclassified) with an `ft_work_type` filter on `GET /entities`, plus type badges in the entity table and detail views. Optional backfill: `backend/scripts/backfill_work_type.py`. (PRs #93, #94, #96)
- **Entity detail-page parity:** The dedicated `/entities/[id]` detail page now surfaces the same enrichment as the table modal — a "Work type" row in *Core Fields* and a "Journal" section with NIF + NIF Bayes (open proxy). (PRs #96, #97)
- **Backfill operations runbook:** `docs/operating/BACKFILL_RUNBOOK.md` — Dokploy playbook for the idempotent `nif_bayes` and `work_type` backfills. (PR #95)
- **Error Boundaries (Sprint 101):** Root `app/error.tsx` component, shared `RouteError`, and route-level wrappers for `entities`, `analytics`, `rag`, `settings`, and `import-export`.
- **Infrastructure:** Docker Compose multi-stage builds initialized for production (`Dockerfile.backend`, `frontend/Dockerfile` non-root user).
- **Automated Testing (Sprint 100):** Frontend testing setup with Vitest and React Testing Library (52 tests across 6 suites covering UI state components, AuthContext, and EntityTable). CI integration to `lint.yml` added.
- **Frontend CI Checks:** TypeScript type-check and ESLint integrated into GitHub Actions.
- **Onboarding Experience (Sprint 95):** Five-step onboarding completion detection (`GET /onboarding/status`), `WelcomeModal` first-login carousel, `OnboardingChecklist` UI, and dynamic empty-state CTA actions.
- **PostgreSQL Support (Sprint 94):** Full dialect-aware migrations and conditional FTS5 vs. GIN indexing. 
- **Embeddable Widgets (Sprint 93):** `EmbedWidget` SDK managing data provisioning across `entity_stats`, `top_concepts`, `recent_entities`, and `quality_score`. Public token verification added.
- **Workflow Automation (Sprint 92):** No-code builder supporting triggers (e.g. `entity.enriched`), conditions, and actions (`send_webhook`, `tag_entity`, etc.).
- **Real-Time Collaboration (Sprint 91):** WebSocket integration for entity changes and presence status updates across active users.
- **Web Scraping Enrichment (Sprint 90):** Configurable CSS/XPath scraper fallback. Target rate defaults and circuit breaker limits.
- **Transformation Engine (Sprint 89):** Safe string/transformation operations replacing 12 built-in generic functions in `eval()`-free way.
- **Clustering Algorithms (Sprint 88):** Extended algorithms including `fingerprint`, `n-gram Jaccard`, `Cologne Phonetic`, and `Metaphone`.
- **Data Faceting (Sprint 87):** OpenRefine-inspired dynamic entity catalog faceting. 
- **Alembic Migrations (Sprint 86.5):** Baseline migration implementation (`0001_baseline.py`) mapping complete database schema.
- **Enhanced Annotations (Sprint 86):** Emoji reactions, message threads, resolve/unresolve state toggles.
- **Multi-Tenant Orgs (Sprint 85):** User to Organization grouping models with free/pro/enterprise delineations.

### Changed
- **System Naming:** Global search & replace switching project branding from `DBDesambiguador` to `UKIP`.
- **Design System Consistency (Sprint 96 & 98):** Global adoption of Unified State components (`Skeleton`, `EmptyState`, `ErrorBanner`). Sweeps replacing inline divs.
- **Security Enhancements (Sprint 101):** Expanded explicit environment variable validation for `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, and `ADMIN_PASSWORD` (rejects weak defaults).
- **Rate-Limiting Security:** `SlowAPI` boundaries added to 10 additional critical endpoint pathways. Header enforcement mapped in backend and CSP configurations in `next.config.ts`.
- **API Documentation:** Generated latest OpenAPI specs to `API.md` (248 live endpoints).

### Fixed
- **Mobile Access:** Responsive grid formatting (`md:grid-cols-3`) extended across RAG Chat and OLAP dashboard cards.
- **Accessibility Adjustments (Sprint 97):** Aria attributes fixed (`aria-modal`, `aria-hidden`) across SVG content and forms. WAI-ARIA roles fully resolved for focus traps and modals.
