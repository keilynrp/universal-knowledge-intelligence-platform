# Tasks — extend report coverage to authority, coauthorship and journals

TDD throughout. Each section is authored once against the format-neutral payload
from `unify-report-format-coverage`; the parity test from that change is the gate
that proves it reached all four formats.

## 0. Prerequisite

- [ ] 0.1 Confirm `unify-report-format-coverage` is merged and its parity test
      has no remaining `xfail`. Do not start otherwise — authoring against the
      old builders means writing each section four times.

## 1. Authority control section

- [ ] 1.1 Failing test: section reports total, confirmed and pending-review
      counts from seeded `AuthorityRecord` rows.
- [ ] 1.2 Implement `collect_authority_control` — aggregate counts, status
      distribution, mean confidence. Scope via `scope_query_to_org`.
- [ ] 1.3 Failing test: unresolved conflicts are listed with confidence and
      `nil_reason`.
- [ ] 1.4 Add the conflicts table block, with an explicit limit.
- [ ] 1.5 Failing test: a backlog produces a prose reliability statement.
- [ ] 1.6 Add the `Narrative` block.
- [ ] 1.7 Failing test: no authority records → explanatory empty state, not a
      zero-conflict finding.
- [ ] 1.8 Test: tenant isolation — another org's records never appear.
- [ ] 1.9 Register the section; parity test picks it up across all four formats.

## 2. Readiness caveat

- [ ] 2.1 Failing test: pending-to-total above threshold adds a backlog caveat
      to the stakeholder reading. (RED — the reading cannot see authority data.)
- [ ] 2.2 Compute the ratio and thread it into
      `_section_stakeholder_reading`.
- [ ] 2.3 Failing test: the observed ratio is always disclosed, above or below
      threshold.
- [ ] 2.4 Failing test: below threshold raises no caveat.
- [ ] 2.5 Surface the threshold as configuration; document the default and that
      it is a starting point, not a derived constant.

## 3. Collaboration graph section

- [ ] 3.1 Failing test: section reports author, edge and community counts from
      seeded `Author` / `CoauthorEdge` / `AuthorStats`.
- [ ] 3.2 Implement `collect_collaboration_graph` reading precomputed
      `AuthorStats`. Scope via `scope_query_to_org`.
- [ ] 3.3 Failing test: most central authors listed with degree, centrality and
      publication count.
- [ ] 3.4 Add the centrality table block.
- [ ] 3.5 Failing test: bridge authors spanning communities are identified.
- [ ] 3.6 Implement bridge detection from precomputed columns only.
- [ ] 3.7 Failing test: rendering issues no graph computation — assert the
      section does not invoke the graph analytics path.
- [ ] 3.8 Failing test: absent or stale `computed_at` → staleness notice.
- [ ] 3.9 Failing test: no author stats → explanatory empty state.
- [ ] 3.10 Test: tenant isolation.
- [ ] 3.11 Register the section.

## 4. Journal portfolio section

- [ ] 4.1 Failing test: section reports distinct journals, DOAJ share and APC
      exposure from seeded `JournalMetric` rows.
- [ ] 4.2 Implement `collect_journal_portfolio`. Scope via
      `scope_query_to_org`.
- [ ] 4.3 Failing test: `nif_bayes` never renders without
      `[nif_ci_low, nif_ci_high]`.
- [ ] 4.4 Implement the top-journals table with the interval bound to the
      estimate so they cannot be separated.
- [ ] 4.5 Failing test: rendered output labels NIF as a field-normalized open
      proxy and never as a Journal Impact Factor.
- [ ] 4.6 Failing test: `works_2yr` is labelled as local coverage.
- [ ] 4.7 Failing test: no journal metrics → explanatory empty state.
- [ ] 4.8 Test: tenant isolation.
- [ ] 4.9 Register the section.

## 5. Surfacing

- [ ] 5.1 The three sections appear in `GET /reports/sections` with per-format
      availability.
- [ ] 5.2 Frontend section picker offers them.
- [ ] 5.3 Translation parity for new UI strings (EN + ES).

## 6. Close out

- [ ] 6.1 Performance check: each new section measured against the largest
      available dataset; document the timings.
- [ ] 6.2 Full backend suite green (`pytest backend/tests/`).
- [ ] 6.3 Frontend gates: ESLint `--max-warnings=0`, Design System governance,
      translation parity.
- [ ] 6.4 Manual check: a report with all three new sections exported in all
      four formats, NIF labelling and credible intervals verified by eye on the
      real artifact.
