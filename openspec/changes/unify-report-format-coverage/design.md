# Design — unify report section coverage across output formats

## Context

Four export paths, one section vocabulary:

| Path | Entry point | Sections honored |
|---|---|---|
| HTML | `report_builder.build()` | 10 |
| PDF | `report_builder.build()` → WeasyPrint | 10 (same string) |
| Excel | `EnterpriseExcelExporter.build()` | 2 conditional + 2 unconditional sheets |
| PPTX | `exporters/pptx_exporter.generate_pptx()` | 4 |

Scheduled reports (`routers/scheduled_reports.py`) reuse the HTML, PDF and Excel
paths and default to the full section list, so the Excel gap compounds on a
recurring schedule.

## The real constraint

`report_builder.py` fuses three responsibilities in every `_section_*` function:

1. query the database,
2. compute derived values (percentages, bars, badges),
3. emit an HTML string.

Because (1) and (2) are only reachable through (3), Excel and PPTX cannot reuse
them. Both re-query the ORM directly — `EnterpriseExcelExporter` even
re-implements `_entities_query` and `_harmonization_query` verbatim from
`report_builder`. That duplication is the mechanism by which the formats drifted,
and it will reproduce itself for every section added in the future.

So the parity problem is not "PPTX is missing six `if` branches". Adding those
branches would triple the duplicated query logic and leave the next section
facing the same four-way cost.

## Decision: a format-neutral section payload

Introduce a narrow intermediate representation. Each section becomes:

```
collect_<section>(db, ctx) -> SectionData
```

where `ctx` carries what the builders already take (`domain_id`, `org_id`,
`benchmark_profile_id`, `benchmark_org`), and `SectionData` is:

```
SectionData:
  key: str                 # "impact_projection"
  title: str               # "Impact Projection"
  blocks: list[Block]

Block = StatGrid | Table | Narrative | Meter
  StatGrid:  items[]  {label, value, sub}
  Table:     columns[], rows[][], optional bar_column
  Narrative: heading, paragraphs[]
  Meter:     label, pct                     # the bar-chart primitive
```

Four primitives cover all ten existing sections. Verified against the current
HTML: stat cards → `StatGrid`; the entity/gap/rule tables → `Table`; the
`callout` executive readings and the stakeholder lens → `Narrative`; the
projection driver bars → `Meter`.

Renderers then implement four small functions each:

- **HTML** — the existing CSS classes, essentially the current markup.
- **Excel** — `StatGrid` → a labelled KPI block; `Table` → a sheet;
  `Narrative` → a wrapped text block; `Meter` → a percentage cell.
- **PPTX** — `StatGrid` → a KPI row; `Table` → a slide table; `Narrative` → a
  bullet slide; `Meter` → a bar shape.

### Why not the cheaper option

Adding the missing `if` branches per format is ~1 day and leaves four
implementations to keep in sync, with no mechanism preventing the next drift.
The payload split is larger but converts "keep four renderers in sync forever"
into "author a section once". Given that change 2 of this track adds at least
three more sections, the cheaper option is more expensive by the second change.

## Migration strategy

Strangler, section by section — the report endpoints stay green throughout:

1. Land `SectionData`, the block types, and the four renderers with the block
   primitives only (no sections migrated). Renderers are unit-tested directly
   against synthetic payloads.
2. Migrate one section at a time. For each: write `collect_*`, point the HTML
   renderer at it, and assert the HTML output is unchanged from the current
   builder. Character-level equality is not required — the existing per-section
   tests plus a structural assertion are the gate.
3. Once a section is migrated, Excel and PPTX pick it up automatically.
4. Delete the old `_section_*` builder only after its replacement is green.

`SECTION_BUILDERS` stays as the public registry so `reports.py`,
`scheduled_reports.py` and the 422 validation keep working untouched during the
migration.

## Unsupported sections

Some sections may still not map cleanly to a format — `agentic_trace` is long
free text that is genuinely poor as a spreadsheet. Rather than silently dropping
it, each renderer declares its supported block types, and a section whose blocks
are unsupported is reported back to the caller.

Delivery mechanism: a response header (`X-UKIP-Report-Omitted-Sections`) on the
binary export endpoints, since those return a file body and cannot carry a JSON
envelope. The section picker reads per-format availability from an extended
`GET /reports/sections`, so the omission is visible before the user exports
rather than only after.

## Risks

| Risk | Mitigation |
|---|---|
| HTML output drifts during migration and regresses briefs already in use | Migrate one section at a time; existing per-section tests must stay green at every step |
| The four primitives prove insufficient for a future section | They are additive — a fifth block type is a renderer change, not a payload redesign |
| Larger diff than a branch-patch fix | Strangler keeps every intermediate state shippable; no big-bang cutover |
| Excel's unconditional Summary/Entities sheets are load-bearing for existing consumers | Keep them emitting by default; make them section-driven without removing the default |
