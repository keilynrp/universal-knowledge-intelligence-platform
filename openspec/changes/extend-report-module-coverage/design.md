# Design — extend report coverage to authority, coauthorship and journals

## Context

Every new section is a `collect_*(db, ctx) -> SectionData` function plus its
registration, per `unify-report-format-coverage`. No renderer work is needed if
the sections stay within the four existing block primitives (`StatGrid`,
`Table`, `Narrative`, `Meter`). All three sections below are designed to do so.

All three read data that already exists and is already tenant-scoped by
`org_id`. Every query MUST go through `scope_query_to_org`, as the existing
sections do — these tables all carry `org_id`, and a report is exactly the
artifact where a cross-tenant leak would be least detectable.

## Section: `authority_control`

Source: `AuthorityRecord` (+ `AuthorityResolveJob` for last-run recency).

| Block | Content |
|---|---|
| `StatGrid` | total records, confirmed, pending review, average confidence |
| `Table` | resolution status distribution with share bars |
| `Table` | top unresolved conflicts — `original_value`, candidate `canonical_label`, `confidence`, `nil_reason` |
| `Narrative` | what the backlog means for this report's reliability |

The `Narrative` block is the point of the section. `review_required = true` with
a large pending count means identity resolution is unfinished, and a reader
deserves that stated in prose rather than inferred from a count.

### The reliability caveat

`_section_stakeholder_reading` already renders a `stance` paragraph derived from
benchmark status. It currently cannot see the authority backlog, so it can say
"comparatively strong position" while thousands of unresolved identities sit
underneath.

Add a backlog signal to the same paragraph, gated on the ratio of pending
authority records to total entities rather than an absolute count — 9k pending
means something very different against 10k entities than against 10M.

Threshold: material at **≥10%** pending-to-total. Chosen as a starting point,
not a derived constant; it is config-surfaced so it can be tuned without a code
change, and the section states the actual ratio so a reader can apply their own
judgement regardless of where the line sits.

## Section: `collaboration_graph`

Source: `Author`, `CoauthorEdge`, `AuthorStats`.

| Block | Content |
|---|---|
| `StatGrid` | authors, edges, communities, mean degree |
| `Table` | most central authors — degree, centrality, publication count, community |
| `Table` | bridge authors — high centrality relative to degree, spanning communities |
| `Narrative` | concentration vs. distribution reading |

`AuthorStats` carries `degree`, `centrality`, `community_id` and
`publication_count` precomputed, so this section is a read, not a graph
computation. If `AuthorStats.computed_at` is stale or absent, the section says
so rather than presenting stale centrality as current — a centrality figure with
no computation date is worse than no figure.

Bridge detection uses the existing precomputed columns; no new graph algorithm
runs at report time. Report generation must not become a compute job.

## Section: `journal_portfolio`

Source: `JournalMetric`, joined to entity publication counts.

| Block | Content |
|---|---|
| `StatGrid` | distinct journals, DOAJ share, mean NIF, total APC exposure |
| `Table` | top journals — publications, NIF, **`nif_bayes` with `[nif_ci_low, nif_ci_high]`**, APC, DOAJ |
| `Narrative` | open-access position and cost exposure |

### Presenting NIF honestly

Non-negotiable for this section:

- `nif_bayes` SHALL always render with its credible interval. The interval is
  not optional detail; it is what makes a low-volume journal's estimate
  interpretable. A point estimate alone invites exactly the overconfidence the
  shrinkage estimator was built to prevent.
- NIF SHALL be labelled as a field-normalized open proxy, **not** as a Journal
  Impact Factor. The distinction is already recorded in the project's own notes
  and must not blur on the artifact that leaves the building.
- `works_2yr` is a local count, not OpenAlex's global two-year count. Where it
  is shown, it is labelled as local coverage, because a reader will otherwise
  assume it is comparable to published figures.

## Empty states

Each section follows the existing convention (`topic_clusters`,
`harmonization_log`): a specific explanatory message naming what to run, not a
blank block and not a zero that reads as a finding. A workspace that never ran
coauthorship should see "no collaboration graph computed yet", never "0
communities".

## Risks

| Risk | Mitigation |
|---|---|
| Authority/journal queries are slow on large workspaces | Aggregate queries with explicit limits, mirroring existing sections; measure against the largest available dataset before merge |
| The reliability caveat fires too often and becomes noise | Ratio-based, config-surfaced threshold; the section always states the actual ratio |
| NIF presented as JIF in an external document | Explicit labelling requirement, asserted by test on rendered output |
| Stale `AuthorStats` presented as current | Section renders `computed_at` and degrades to a staleness notice when absent |
| Cross-tenant leakage in a distributed artifact | Every query through `scope_query_to_org`; per-section isolation tests |
