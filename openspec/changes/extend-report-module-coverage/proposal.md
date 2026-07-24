# Extend report coverage to authority, coauthorship and journals

> **Priority: 2 of 2** (reporting-coverage track)
> **Depends on:** `unify-report-format-coverage`. That change makes a section
> authorable once and rendered by all four formats. Landing new sections before
> it means writing each of them four times — or, more realistically, writing
> them for HTML only and widening the parity gap this track exists to close.
> **Blocks:** nothing.

## Why

The report layer reads five models: `RawEntity`, `EntityRelationship`,
`HarmonizationLog`, `AnalysisContext` and `CatalogPortal`. The platform defines
sixty-five. Three delivered subsystems that carry real analytical weight have
no representation in any report format.

**Authority control and disambiguation.** `AuthorityRecord` and its supporting
tables back the whole disambiguation track — blocking, scoring, review
thresholds, write-back to canonical IDs. Production currently holds roughly
9.4k authority records awaiting human review. A brief can state that the
dataset is "decision-ready" while thousands of unresolved identity conflicts sit
underneath it, because no section looks. The `review_required`, `nil_reason` and
`resolution_route` columns exist precisely to express that uncertainty and are
never surfaced to a reader.

**Coauthorship and the collaboration graph.** `Author`, `CoauthorEdge` and
`AuthorStats` carry degree, centrality, community assignment and publication
counts. For a research office or a transfer office, the collaboration structure
*is* the finding — who bridges communities, which clusters are isolated, where
partnership capacity concentrates. `EntityRelationship` reaches reports only
indirectly, as graph-bridge signals inside `hidden_patterns`. The author graph
does not reach them at all.

**Journal metrics.** `JournalMetric` holds field-normalized impact
(`normalized_impact_factor` against `nif_field`), the Bayesian shrunk estimate
with its credible interval (`nif_bayes`, `nif_ci_low`, `nif_ci_high`), APC cost
data and DOAJ status. Two full workstreams produced this. A publication
portfolio brief that cannot say where the work was published, at what open-access
cost, or with what field-normalized standing, is omitting the question
stakeholders ask first.

The pattern is consistent: work ships to the API and the dashboards, and the
reporting layer — the surface that actually leaves the building and reaches a
decision-maker — is not extended with it. Each of these subsystems is queryable
today; the gap is a reporting gap, not a data gap.

The Bayesian metrics deserve particular care. `nif_bayes` exists because the raw
NIF is unstable for low-volume journals, and the credible interval is the
honest expression of that. A report that prints a point estimate without its
interval would misrepresent the very uncertainty the estimator was built to
show.

## What Changes

Three new sections, authored against the format-neutral payload from change 1,
therefore available in HTML, PDF, Excel and PPTX on arrival:

- **`authority_control`** — resolution status distribution, review backlog size,
  confidence distribution, top unresolved conflicts by impact, and a plain
  statement of what the backlog means for the report's own reliability.
- **`collaboration_graph`** — author and edge counts, community count, the most
  central authors by degree and centrality, bridge authors connecting otherwise
  separate communities, and isolated clusters.
- **`journal_portfolio`** — publication distribution across journals, NIF with
  its Bayesian estimate **and credible interval**, APC exposure with DOAJ
  status, and open-access position.

Plus:

- **A reliability caveat that travels with the report.** When the authority
  backlog is material relative to dataset size, the stakeholder reading SHALL
  say so, so readiness language cannot contradict a known identity-resolution
  backlog sitting underneath it.
- **Empty-state handling per section**, matching the existing convention: a
  workspace that never ran coauthorship gets an explanatory message, not a
  broken or misleadingly empty section.

## Non-Goals

- No changes to how authority, coauthorship or journal data is computed. This
  change reads existing data and does not touch the resolution, graph or NIF
  pipelines.
- No new enrichment or backfill. Sections reflect whatever the workspace has.
- The remaining uncovered modules — retrospective events, OpenAlex lake,
  annotations, audit log, data lifecycle, workflows — are deliberately out of
  scope. They are operational and governance surfaces rather than analytical
  findings, and warrant a separate decision about whether a stakeholder brief is
  the right place for them at all.
