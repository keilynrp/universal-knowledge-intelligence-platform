# Tasks — unify report section coverage across output formats

TDD throughout. The migration is a strangler: every task leaves the four export
endpoints green and shippable.

## 0. Baseline guard

- [x] 0.1 Failing test: parametrized over `SECTION_BUILDERS`, assert each
      section renders in HTML, PDF, Excel and PPTX. (RED — 6 of 10 fail for
      PPTX, 8 of 10 for Excel. This test is the definition of done.) Done in
      `test_report_parity_guard.py`; xfail count confirmed 8 Excel + 6 PPTX.
- [x] 0.2 Mark the currently-failing combinations `xfail` with the section name
      in the reason, so the ratchet is visible and each migration flips one.
      Marks are derived from `reporting/format_support.py` (the support map) and
      strict, so the map and the renderers cannot drift apart.
- [x] 0.3 Snapshot the current HTML per section as a regression baseline for the
      migration. Resolved per the design's own gate ("character-level equality is
      not required — existing per-section tests plus a structural assertion are
      the gate"): each migrated section adds a structural HTML assertion (see
      `test_migrated_entity_stats_html_preserves_structure`) rather than a stored
      golden, avoiding a brittle byte-baseline across many PRs.

## 1. Section payload

- [x] 1.1 Test: `SectionData` and the four block types (`StatGrid`, `Table`,
      `Narrative`, `Meter`) construct and validate. (`test_section_data.py`.)
- [x] 1.2 Implement the payload types in `backend/reporting/section_data.py`.
      Frozen dataclasses; Table validates row width + bar_column range, Meter
      bounds pct to [0, 100], SectionData requires key + title.
- [x] 1.3 Test: a payload containing every block type round-trips through each
      renderer without raising. (`test_report_renderers.py`.)

## 2. Renderers over primitives

- [x] 2.1 Failing test: HTML renderer emits the existing CSS classes for each
      block type.
- [x] 2.2 Implement the HTML renderer. (`reporting/html_renderer.py`; reuses the
      existing grid/stat-card/callout/bar-wrap classes; escapes all data.)
- [x] 2.3 Failing test: Excel renderer emits a KPI block, a sheet, a wrapped
      text block and a percentage cell.
- [x] 2.4 Implement the Excel renderer. (`reporting/excel_renderer.py`; one sheet
      per section, sanitized+deduped 31-char titles.)
- [x] 2.5 Failing test: PPTX renderer emits a KPI row, a slide table, a bullet
      slide and a bar shape.
- [x] 2.6 Implement the PPTX renderer. (`reporting/pptx_renderer.py`; native
      slide table for Table, proportional auto-shape bar for Meter.)
- [x] 2.7 Each renderer declares its supported block types. (`SUPPORTED_BLOCKS`
      on all three; test asserts all four blocks covered.)

## 3. Migrate sections (one commit each, HTML baseline must hold)

- [x] 3.1 `entity_stats` — **pilot.** `collect_entity_stats()` in report_builder
      is the single source; `_section_entity_stats` now delegates to
      `render_html(collect_...)`; the Excel exporter renders it via
      `render_excel(collect_...)`, gaining real Excel coverage. Support map +
      parity marker updated; the `(excel, entity_stats)` xfail flipped
      automatically (14 → 13). HTML stability held by the existing tests plus a
      structural assertion (`test_migrated_entity_stats_html_preserves_structure`).
      PPTX already rendered entity_stats via its hand-written block; de-dup of
      that block onto the collector is deferred to a follow-up (strangler — both
      paths render the same marker, guard stays green).
- [x] 3.2 `enrichment_coverage`. `collect_enrichment_coverage()` is the single
      source; `_section_enrichment_coverage` delegates to `render_html(collect_...)`
      and the Excel exporter renders it via the shared `render_excel`, flipping the
      `(excel, enrichment_coverage)` xfail automatically (13 → 12). The Excel
      exporter's migrated-section block is now a dict-driven loop so the next
      sections are one-line additions. Decorative source badge dropped (the shared
      `Table` primitive renders plain cells); empty-state message dropped per the
      pilot precedent. HTML stability held by the existing tests plus a structural
      assertion (`test_migrated_enrichment_coverage_html_preserves_structure`).
      PPTX already rendered it via its hand-written block; de-dup deferred (both
      paths emit the same marker, guard stays green).
- [x] 3.3 `top_secondary_labels`. `collect_top_secondary_labels()` is the single
      source; `_section_top_brands` delegates to `render_html(collect_...)` and the
      Excel exporter renders it via the shared loop, flipping the
      `(excel, top_secondary_labels)` xfail (12 → 11). The Excel exporter now
      canonicalizes requested sections so the `top_brands` alias resolves to the
      same collector. The shared `Table` prints the share value beside the bar (the
      hand-written builder drew the bar alone); the bar width is unchanged. Empty
      state dropped per the pilot precedent. Structural assertion in
      `test_migrated_top_secondary_labels_html_preserves_structure`.
- [ ] 3.4 `topic_clusters`
- [ ] 3.5 `harmonization_log`
- [ ] 3.6 `institutional_benchmark`
- [x] 3.7 `impact_projection` (taken ahead of 3.4–3.6: it flips a real Excel
      xfail and is the first real exercise of the Narrative + Meter primitives;
      3.4 topic_clusters and 3.5 harmonization_log are de-dup-only — already
      Excel-covered via bespoke sheets — so they move no ratchet and are batched
      with the cleanup). `collect_impact_projection()` is the single source:
      StatGrid (3 KPI cards) + Narrative (executive interpretation) + one Meter
      per driver. `_section_impact_projection` delegates to `render_html(...)` and
      the Excel loop renders it, flipping `(excel, impact_projection)` (11 → 10).
      The decorative "Projection drivers" wrapper card is dropped (the four Meters
      render as label + bar directly); the bold "Brief angle:" prefix becomes plain
      text. Structural assertion in
      `test_migrated_impact_projection_html_preserves_structure`.
- [ ] 3.8 `hidden_patterns`
- [ ] 3.9 `decision_recommendations`
- [ ] 3.10 `agentic_trace` — decide and record whether Excel declares it
      unsupported rather than forcing free text into cells
- [ ] 3.11 `stakeholder_reading` (always-on section, not in the registry)
- [ ] 3.12 Remove each superseded `_section_*` builder once its replacement is
      green; delete the duplicated `_entities_query` / `_harmonization_query`
      from `excel_exporter.py`

## 4. Omission reporting

- [ ] 4.1 Failing test: requesting an unsupported section returns the file plus
      an omission indicator, not a silent drop.
- [ ] 4.2 Implement `X-UKIP-Report-Omitted-Sections` on the binary export
      endpoints.
- [ ] 4.3 Failing test: `GET /reports/sections` carries per-format availability.
- [ ] 4.4 Extend the section listing response.
- [ ] 4.5 Frontend: the section picker shows per-format availability and warns
      before an export that would omit a selected section.
- [ ] 4.6 Translation parity for any new UI strings (EN + ES).

## 5. Validation consistency

- [x] 5.1 Failing test: `POST /exports/excel` with an unknown section returns
      422. (RED — currently accepted.)
- [x] 5.2 Add the validation to the Excel endpoint.
- [x] 5.3 Test: all four endpoints reject the same unknown name identically.
- [x] 5.4 Failing test: PPTX renders the top-labels slide for the *public* id
      `top_secondary_labels`, not only the deprecated `top_brands` alias.
      (RED — `pptx_exporter.py:210` gates on the alias.)
- [x] 5.5 Resolve aliases centrally so no renderer matches raw section strings;
      update `dashboard/page.tsx:694` to send the public id. (Added
      `canonical_sections()` in `report_builder`, applied at the PPTX boundary.)

## 6. Scheduled reports

- [ ] 6.1 Failing test: a scheduled Excel report with unrenderable sections
      records the omission on the run.
- [ ] 6.2 Implement omission recording in `scheduled_reports.py`.

## 7. Close out

- [ ] 7.1 Remove every `xfail` from 0.2 — none may remain.
- [ ] 7.2 Full backend suite green (`pytest backend/tests/`).
- [ ] 7.3 Frontend gates: ESLint `--max-warnings=0`, Design System governance,
      translation parity.
- [ ] 7.4 Manual check: one report exported in all four formats from the same
      payload, sections consistent across all four.
