## Why

A report generated in English contains Spanish. From a real production report (`ukip_report_science_20260729`), the Hidden Patterns section reads *"Concentración temática: Political science"* with the action *"Explorar este cluster como posible lente narrativo o línea estratégica"* — surrounded by English headings and English sections. Password-reset emails go out with the subject `"{platform_name}: recupera tu contraseña"` regardless of who receives them.

This is not a translation backlog. The backend has **no i18n mechanism at all**: no message catalog, no locale resolution, no way for a caller to request a language. `POST /reports/generate` cannot be told which language to produce, and the `User` model has no language field, so there is nowhere for a preference to live server-side.

Meanwhile the frontend already has the shape of the answer — `frontend/app/i18n/translations.ts`, one flat key space, EN and ES, 3,402 keys each and currently at exact parity. What it does **not** have is a gate: nothing in CI, in the test suite, or in the type system checks that a key lands in both languages. `LanguageContext.tsx` casts the catalog to `Record<Language, Record<string, string>>`, which erases the structural check TypeScript would otherwise give. Today's parity is a fact about the current file, held by discipline, not an invariant anything enforces. Translating the offending backend strings in place would just make them English instead of Spanish, still with no way to serve a Spanish-speaking reader, and still with nothing stopping the next one-sided string from being committed on either side.

Server-rendered artefacts are why this cannot be solved on the client: reports (PDF, PPTX, Excel) and emails are produced in the backend and never pass through the frontend, so "let the frontend translate it" does not reach them.

## What Changes

- Introduce a **backend message catalog** keyed compatibly with the frontend's, so a string is defined once rather than twice.
- Add **per-request locale resolution** with an explicit precedence chain, and a `language` field on report generation so an operator can ask for a report in a given language.
- Migrate **user-facing labels, operator-facing messages, and email subjects** to catalog keys in both languages.
- Build the **EN/ES parity gate** — it does not exist yet — covering the backend catalog and the frontend one it projects from, so a string cannot ship in one language only on either side.

Deliberately **out of scope** (decided with the product owner):

- **Generated analysis text stays English.** Sentences the system composes from data (`f"Concentración temática: {concept}"`, recommendations, findings) are not localised. The concepts inside them come from OpenAlex in English, so a Spanish sentence would still cite "Political science" — a mixed result for a large amount of work. A reader gets a document in their language with proper nouns in the source language, which is the norm in scientific literature.
- **Data values are never translated.** Concept names, journal titles, author names and institution names pass through as the provider supplies them.

This boundary is the crux of the change and is recorded as a requirement, not a footnote — without it, "backend i18n" silently expands into "generate analysis in a language".

## Capabilities

### New Capabilities
- `backend-message-catalog`: a keyed message store shared with the frontend catalog, its file layout, key naming, interpolation rules, and the EN/ES parity gate that covers it.
- `backend-locale-resolution`: how a request's language is determined — explicit parameter, then request header, then configured default — and how report generation and outbound email consume it.

### Modified Capabilities
<!-- None. No published spec currently states anything about backend language,
     so nothing existing changes its requirements. The report presentation
     contract deliberately excludes language (it governs what a report states
     about its figures, not which language it states it in). -->

## Impact

- **New**: a catalog module under `backend/i18n/`, its EN and ES resource files, and a resolver used by routers, workers and exporters.
- **Modified**: the ~16 backend modules currently holding Spanish literals, chiefly `services/domain_neutral_labels.py`, `services/audience_presets.py`, `enrichment_worker.py`, `services/impact_projection.py`, `services/pattern_discovery.py`, `services/field_correspondence.py`, `routers/auth_users.py` (email subjects) and `routers/dashboards.py`.
- **API**: `POST /reports/generate` gains an optional language parameter; the OpenAPI contract and the generated SDK clients change with it.
- **CI**: a translation parity gate is added. There is none today — this is new CI surface, not an extension, and it covers the frontend catalog as well, since gating a projection whose source is ungated would prove nothing.
- **Not changed**: the frontend catalog's own contents, and any analysis-generating code path — those keep emitting English prose.

An accurate inventory of the strings is part of the work, not an input to it. Two heuristic counts disagree (96 across 17 modules on 2026-07-29; 71 across 16 on 2026-07-31) and both include false positives — module docstrings that merely contain an accented word such as "Cramér's V" or the phrase "English and Spanish names". The first task is a classified inventory, so the migration operates on a list that has been read rather than pattern-matched.
