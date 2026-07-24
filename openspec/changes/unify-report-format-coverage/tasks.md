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
- [ ] 0.3 Snapshot the current HTML per section as a regression baseline for the
      migration. **Deferred to the migration slice (phase 3)** — the baseline is
      only consumed when a builder is replaced; generating it now would leave a
      stale golden sitting across several PRs. The parity guard's HTML honesty
      checks and the existing per-section tests hold HTML stable until then.

## 1. Section payload

- [x] 1.1 Test: `SectionData` and the four block types (`StatGrid`, `Table`,
      `Narrative`, `Meter`) construct and validate. (`test_section_data.py`.)
- [x] 1.2 Implement the payload types in `backend/reporting/section_data.py`.
      Frozen dataclasses; Table validates row width + bar_column range, Meter
      bounds pct to [0, 100], SectionData requires key + title.
- [ ] 1.3 Test: a payload containing every block type round-trips through each
      renderer without raising. **Deferred to the renderer slice (phase 2)** —
      the round-trip needs the renderers to exist.

## 2. Renderers over primitives

- [ ] 2.1 Failing test: HTML renderer emits the existing CSS classes for each
      block type.
- [ ] 2.2 Implement the HTML renderer.
- [ ] 2.3 Failing test: Excel renderer emits a KPI block, a sheet, a wrapped
      text block and a percentage cell.
- [ ] 2.4 Implement the Excel renderer.
- [ ] 2.5 Failing test: PPTX renderer emits a KPI row, a slide table, a bullet
      slide and a bar shape.
- [ ] 2.6 Implement the PPTX renderer.
- [ ] 2.7 Each renderer declares its supported block types.

## 3. Migrate sections (one commit each, HTML baseline must hold)

- [ ] 3.1 `entity_stats`
- [ ] 3.2 `enrichment_coverage`
- [ ] 3.3 `top_secondary_labels`
- [ ] 3.4 `topic_clusters`
- [ ] 3.5 `harmonization_log`
- [ ] 3.6 `institutional_benchmark`
- [ ] 3.7 `impact_projection`
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
