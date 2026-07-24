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

> **PPTX wiring (deviation from design step 3).** The design assumed "Excel and
> PPTX pick a migrated section up automatically." Excel does — it renders every
> migrated collector through the shared `render_excel` loop. PPTX does **not**:
> `generate_pptx` renders its own hand-written slide blocks, so each migrated
> section had to be wired explicitly into a `render_pptx(collect_...)` loop.
> Done for `impact_projection`, `institutional_benchmark`, `hidden_patterns`,
> `decision_recommendations` (their `(pptx, …)` xfails flipped). The three
> pre-existing hand-written PPTX blocks (`entity_stats`, `enrichment_coverage`,
> `top_secondary_labels`) are hand-tuned and left in place; replacing them with
> the generic renderer is a deliberate design call deferred to the cleanup (3.12).

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
- [~] 3.4 `topic_clusters` — **intentionally NOT migrated (decision 2026-07-24).**
      It is already fully covered in every format (HTML/PDF hand-written with a
      concept **chip cloud**, Excel via the rich `_write_concepts` sheet, PPTX via
      the "Top Concepts" slide), so it moves no ratchet. Migrating its HTML onto
      the shared `Table` would drop the prominent chip cloud for only
      code-uniformity, and folding its Excel onto the collector would strip the
      Rank/Percentage columns and the full concept list down to a top-10 summary.
      Kept as-is deliberately; the chips and the richer Excel sheet are the
      point. See 3.12.
- [~] 3.5 `harmonization_log` (HTML + PPTX done; Excel intentionally kept rich —
      see 3.12).
      `collect_harmonization_log()` is the single source: a Table
      (Step/Records Updated/Status/Executed). `_section_harmonization_log`
      delegates to `render_html(...)` and the PPTX loop renders it, flipping the
      last `(pptx, harmonization_log)` xfail. The Applied/Reverted status badge
      becomes a plain Status column; empty state dropped per precedent. Excel still
      renders it via the bespoke "Harmonization" sheet — de-duping that onto the
      collector (and the resulting sheet rename) is deferred to the cleanup (3.12).
      Structural assertion in `test_migrated_harmonization_log_html_preserves_structure`.
- [x] 3.6 `institutional_benchmark`. `collect_institutional_benchmark()` is the
      single source: StatGrid (Profile/Readiness/Status) + Narrative (executive
      reading) + a gaps Table + a rules Table. Status/priority/pass badges become
      plain text. Flips `(excel, institutional_benchmark)`. Structural assertion in
      `test_migrated_institutional_benchmark_html_preserves_structure`.
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
- [x] 3.8 `hidden_patterns`. `collect_hidden_patterns()` is the single source: a
      Narrative (executive reading) + a Table of signals with the impact score as
      the bar column. The per-card confidence badge becomes a plain Confidence
      column. Flips `(excel, hidden_patterns)`. Structural assertion in
      `test_migrated_hidden_patterns_html_preserves_structure`.
- [x] 3.9 `decision_recommendations`. `collect_decision_recommendations()` is the
      single source: a prioritized recommendation Table
      (Priority/Category/Recommendation/Detail/Evidence). The per-card priority
      badge becomes a plain Priority column; the card grid becomes a table. Flips
      `(excel, decision_recommendations)`. Structural assertion in
      `test_migrated_decision_recommendations_html_preserves_structure`.
- [x] 3.10 `agentic_trace` — **declared unsupported for the binary formats.**
      Decision: agentic_trace is long, free-form Q&A audit text that reads poorly
      in a spreadsheet *and* as slide bullets, so Excel and PPTX both declare it
      unsupported; it renders only in HTML/PDF (the existing hand-written
      `_section_agentic_trace`, unchanged). This formalizes the pre-existing
      reality (it already rendered in neither binary format) and pairs it with the
      §4 omission reporting so the drop is reported, not silent. No collector is
      introduced.
- [x] 3.11 `stakeholder_reading` (always-on section, not in the registry).
      `collect_stakeholder_reading()` is the single source: one Narrative framing
      the brief for the chosen audience. `_section_stakeholder_reading` delegates
      to `render_html(...)`. HTML-only (as before — it is prepended in `build()`,
      not part of the binary exporters' section loops, so the ratchet is
      unaffected). The attention-point `<ul>` flattens to paragraphs and the bold
      labels become plain text, per the migration precedent. Structural assertion
      in `test_migrated_stakeholder_reading_html_preserves_structure`.
- [~] 3.12 **Re-scoped (decision 2026-07-24): keep the rich bespoke Excel writers;
      do NOT de-dup.** The premise here — "the collectors supersede the bespoke
      Excel writers" — turned out false. `_write_concepts` (Rank/Concept/Count/
      Percentage%, full list) and `_write_harmonization` (7 columns, up to 200
      rows) produce materially **richer** output than the shared collectors, which
      are sized for a one-page brief (top-10, fewer columns). Folding Excel onto
      the collectors would regress the one format where users open the file *to get
      the full data*. So the bespoke writers stay, and `_entities_query` /
      `_harmonization_query` remain in use (Summary/Entities/Concepts/Harmonization
      sheets), i.e. nothing is deleted. The `_section_*` builders are also not
      "superseded" — each is now a thin delegate to `render_html(collect_...)` and
      is still the registry entry HTML/PDF needs. **Note the surviving asymmetry it
      documents:** for `harmonization_log` (and, had 3.4 been done, `topic_clusters`),
      HTML/PDF + PPTX render the lean shared payload while Excel renders its own
      richer sheet — deliberate, because Excel's audience wants detail. The only
      real duplication left (the collector query vs. the bespoke Excel query) is the
      price of that richer Excel, and is accepted.

## 4. Omission reporting

- [x] 4.1 Failing test: requesting an unsupported section returns the file plus
      an omission indicator, not a silent drop. (`test_report_omissions.py`:
      Excel/PPTX with `agentic_trace` → 200 + header names it; a fully-supported
      request carries no header.)
- [x] 4.2 Implement `X-UKIP-Report-Omitted-Sections` on the binary export
      endpoints. (`reports.py` `_omission_headers()` over
      `format_support.unsupported_sections`; added to `/exports/excel` and
      `/exports/pptx`; header added to CORS `expose_headers` in `main.py`.)
- [x] 4.3 Failing test: `GET /reports/sections` carries per-format availability.
- [x] 4.4 Extend the section listing response. (Each row now carries a `formats`
      map `{html, pdf, excel, pptx} → bool`; additive, existing id/label consumers
      unaffected.)
- [ ] 4.5 Frontend: the section picker shows per-format availability and warns
      before an export that would omit a selected section. (Deferred — backend
      contract is live; frontend is a separate change.)
- [ ] 4.6 Translation parity for any new UI strings (EN + ES). (With 4.5.)

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

- [x] 7.1 Remove every `xfail` from 0.2 — none may remain. The parity guard no
      longer xfails: each combo is asserted directly — supported → the marker must
      render; unsupported → the export must succeed and the section must be named
      by `unsupported_sections()` (the omission contract). agentic_trace is the
      sole declared-unsupported section. Ratchet is at zero.
- [ ] 7.2 Full backend suite green (`pytest backend/tests/`).
- [ ] 7.3 Frontend gates: ESLint `--max-warnings=0`, Design System governance,
      translation parity.
- [ ] 7.4 Manual check: one report exported in all four formats from the same
      payload, sections consistent across all four.
