# Unify report section coverage across output formats

> **Priority: 1 of 2** (reporting-coverage track)
> **Depends on:** the `decision_recommendations` section fix (already shipped on
> `fix/report-decision-recommendations-section`) — that defect had to be cleared
> before the section set could be treated as a stable contract.
> **Blocks:** nothing. Change 2 (`extend-report-module-coverage`) adds *new*
> sections and should land after this one so the new sections inherit parity by
> construction instead of being retrofitted into four renderers.

## Why

UKIP advertises one section picker and four delivery formats. The picker is the
same in all four cases; what comes out is not.

`GET /reports/sections` returns ten selectable sections. Only two of the four
formats can render all ten:

| Section | HTML | PDF | Excel | PPTX |
|---|---|---|---|---|
| `entity_stats` | yes | yes | always on, not selectable | yes |
| `enrichment_coverage` | yes | yes | partial (folded into Summary) | yes |
| `topic_clusters` | yes | yes | yes | yes |
| `harmonization_log` | yes | yes | yes | **no** |
| `top_secondary_labels` | yes | yes | **no** | **no** (alias only, see below) |
| `institutional_benchmark` | yes | yes | **no** | **no** |
| `impact_projection` | yes | yes | **no** | **no** |
| `hidden_patterns` | yes | yes | **no** | **no** |
| `decision_recommendations` | yes | yes | **no** | **no** |
| `agentic_trace` | yes | yes | **no** | **no** |

HTML and PDF are identical because both call `report_builder.build()`. Excel
(`EnterpriseExcelExporter.build`) branches on exactly two section names and
writes its Summary and Entities sheets unconditionally. PPTX (`generate_pptx`)
branches on exactly four.

Three consequences, in increasing order of severity:

1. **The five intelligence sections are HTML/PDF-only.** Institutional
   benchmark, impact projection, hidden patterns, suggested next actions and the
   agentic research trace — the sections that carry the analytical argument, and
   the ones a stakeholder deck most needs — cannot reach PowerPoint or Excel at
   all.

2. **The drop is silent.** A user selects nine sections, requests PPTX, and
   receives a deck containing four. Nothing in the response, the filename, or
   the deck says anything was omitted. The same payload sent to `/exports/pdf`
   and `/exports/pptx` produces two documents that disagree about what the
   portfolio says, with no indication why.

3. **PPTX gates one section on a name the public API never returns.**
   `pptx_exporter.py:210` checks `if "top_brands" in sections`, but
   `top_brands` is the deprecated alias that `GET /reports/sections`
   deliberately excludes — the public id is `top_secondary_labels`. A client
   built against the documented vocabulary therefore never receives that slide.
   It works today only because the dashboard hardcodes the alias
   (`dashboard/page.tsx:694`). Any correct client is silently wrong.

4. **`/exports/excel` does not validate section names at all.** The other three
   endpoints reject unknown sections with a 422 listing the valid set
   (`reports.py:115`, `:160`, `:223`). Excel skips that check, so a typo, a
   stale client, or a renamed section is accepted silently and yields a workbook
   missing content the caller believes it requested.

The alias split is the same failure as the rest, one layer down: the section
vocabulary is re-declared in each renderer instead of shared, so a rename in one
place silently disconnects another.

This also reaches scheduled reports: `scheduled_reports.py` supports
`html`/`pdf`/`excel` and defaults to *all* sections when none are configured, so
a recurring Excel report silently delivers a fraction of its configured content
on every run, indefinitely.

The root cause is architectural, not a set of missing branches. Each section's
data extraction is fused to its HTML string in `report_builder.py`, so any other
format must re-query and re-render from scratch. That is why Excel and PPTX
implemented a subset: the cost of each additional section is a full
reimplementation. Adding sections without fixing this multiplies the gap by
four.

## What Changes

- **Split section data from section presentation.** Each section gains a
  `collect_*(db, ctx) -> SectionData` function returning a structured,
  format-neutral payload (title, key/value stats, tabular rows, narrative
  blocks). The existing HTML builders become renderers over that payload. This
  is the change that makes parity cheap and keeps it cheap.
- **One renderer per format over the shared payload.** HTML/PDF, Excel and PPTX
  each implement a renderer for the payload's block primitives, so a new section
  is authored once and appears in all four formats.
- **Declare per-format capability explicitly.** A format that genuinely cannot
  represent a section (a narrative block has no natural Excel cell form) SHALL
  declare that, and the response SHALL report which requested sections were not
  rendered instead of dropping them silently.
- **Give `/exports/excel` the same 422 validation** as the other three export
  endpoints.
- **Cover the parity contract with a test that enumerates
  `SECTION_BUILDERS`**, so a section added later cannot ship in one format only
  — the test fails until every format either renders it or declares it
  unsupported.

## Non-Goals

- No new sections. New module coverage (authority, coauthorship, journals) is
  change 2 of this track.
- No visual redesign of any format. Parity of *content*, not restyling.
- No change to the section picker UI beyond surfacing per-format availability.
