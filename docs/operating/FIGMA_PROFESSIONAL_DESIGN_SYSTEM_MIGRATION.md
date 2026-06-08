# Figma Professional Design System Migration

## Purpose and Scope

This runbook governs the one-time migration of UKIP semantic color variables
from two Figma Starter collections into one Figma Professional multi-mode
collection. It covers variable creation, value and binding validation,
deprecation, rollback, evidence capture, and approval. It does not change
primitive colors, dimensions, component contracts, or CSS token values.

- Figma team: `Key's team`
- Figma file: `UKIP Design System`
- File URL: <https://www.figma.com/design/noqJwfKV1ihlyfg9y65St7>
- Source collections: `UKIP/Color/Light` and `UKIP/Color/Dark`
- Target collection: `UKIP/Color`
- Target modes: `Light` and `Dark`

## Preconditions

Do not begin mutation until every item is complete.

- [ ] Figma Professional is active for `Key's team`, and the file supports
      multiple modes in one variable collection.
- [ ] The current CSS token audit passes at the repository revision recorded in
      the migration evidence.
- [ ] A current Figma variable inventory export or inspection is recorded,
      including collection IDs, mode IDs, variable IDs, names, aliases, scopes,
      values, and `WEB` code syntax.
- [ ] The inventory confirms 20 identically named semantic variables in each of
      `UKIP/Color/Light` and `UKIP/Color/Dark`.
- [ ] The inventory confirms the source semantic variables alias approved
      variables in `UKIP/Primitives`.
- [ ] A migration owner and a separate design-system reviewer are named.
- [ ] No parallel Figma mutations are in progress. Announce and enforce a
      mutation freeze for this file until migration or rollback is complete.
- [ ] Every component, component set, instance, style, and direct node binding
      that references either Starter semantic collection is inventoried. The
      consumer ledger records the consumer ID, property, source variable ID,
      source collection, page or library location, and intended target variable
      ID so each binding can be migrated, validated, and restored.
- [ ] A rollback evidence location is prepared for affected node, style,
      component, collection, mode, and variable IDs.

## Semantic Mapping Checklist

For every row, recreate the exact variable name in `UKIP/Color`, preserve its
alias to `UKIP/Primitives`, preserve its applicable scopes, and set the exact
Figma `WEB` code syntax shown below.

| Done | Semantic variable | `WEB` code syntax |
| --- | --- | --- |
| [ ] | `color/background/default` | `var(--ukip-bg)` |
| [ ] | `color/background/elevated` | `var(--ukip-bg-elevated)` |
| [ ] | `color/surface/default` | `var(--ukip-surface)` |
| [ ] | `color/panel/default` | `var(--ukip-panel)` |
| [ ] | `color/panel/strong` | `var(--ukip-panel-strong)` |
| [ ] | `color/border/default` | `var(--ukip-border)` |
| [ ] | `color/border/strong` | `var(--ukip-border-strong)` |
| [ ] | `color/text/default` | `var(--ukip-text)` |
| [ ] | `color/text/strong` | `var(--ukip-text-strong)` |
| [ ] | `color/text/muted` | `var(--ukip-muted)` |
| [ ] | `color/text/muted-soft` | `var(--ukip-muted-soft)` |
| [ ] | `color/action/primary` | `var(--ukip-primary)` |
| [ ] | `color/action/primary-strong` | `var(--ukip-primary-strong)` |
| [ ] | `color/action/primary-soft` | `var(--ukip-primary-soft)` |
| [ ] | `color/accent/violet` | `var(--ukip-violet)` |
| [ ] | `color/accent/cyan` | `var(--ukip-cyan)` |
| [ ] | `color/status/success` | `var(--ukip-emerald)` |
| [ ] | `color/status/warning` | `var(--ukip-warning)` |
| [ ] | `color/status/danger` | `var(--ukip-danger)` |
| [ ] | `color/focus/ring` | `var(--ukip-focus-ring)` |

## Exact Migration Procedure

Perform these steps sequentially under the mutation freeze.

1. Record the migration start time, operator, Figma file version, repository
   revision, audit result, and pre-migration inventory location.
2. Create the variable collection `UKIP/Color`.
3. Create modes named exactly `Light` and `Dark`. Record the new collection and
   mode IDs.
4. For each row in the semantic mapping checklist, create one variable in
   `UKIP/Color` with the exact existing name. Do not rename, normalize, or add a
   prefix or suffix.
5. Copy the variable type, description, hidden-from-publishing setting, and all
   applicable scopes from the paired Starter variables.
6. For the `Light` mode, recreate the alias from the corresponding variable in
   `UKIP/Color/Light`. For the `Dark` mode, recreate the alias from the
   corresponding variable in `UKIP/Color/Dark`. Alias the same primitive
   variable; do not replace an alias with a copied literal value.
7. Set the variable's `WEB` code syntax to the exact string in the checklist.
8. Compare all 20 target `Light` resolved values with `UKIP/Color/Light` and all
   20 target `Dark` resolved values with `UKIP/Color/Dark`. Record both source
   and target values, alias IDs, scopes, and syntax. Resolve every mismatch
   before continuing.
9. Create a disposable API smoke-test probe frame that is not a library
   component. Add
   independently inspectable probe layers for:
   - fill bindings;
   - stroke bindings;
   - text fill bindings.
10. Bind every target variable to each applicable probe property. Use separate
    probe layers where a variable's scope does not permit all three properties;
    never broaden a scope merely to make a probe pass.
11. Switch the probe frame between `Light` and `Dark`. Confirm each property
    remains bound to the same target variable ID and resolves to the expected
    mode value. Record inspection evidence and screenshots for both modes. The
    probes verify variable-binding APIs only; they are not evidence that real
    consumers were migrated successfully.
12. Using the pre-migration consumer ledger, rebind every component, component
    set, instance, style, and direct node binding that references
    `UKIP/Color/Light` or `UKIP/Color/Dark` to the matching variable in
    `UKIP/Color`. After each rebind, record the consumer ID, property, original
    source variable ID, target variable ID, operator, and completion status.
13. Validate every rebound consumer in both `Light` and `Dark`. Confirm the
    expected resolved value, visual result, explicit mode behavior, and target
    variable ID. Record the result against each consumer ledger entry.
14. Search or inspect the entire file and published library for remaining
    references to either Starter semantic collection. Reconcile the result
    against the ledger. Zero unaccounted Starter references are permitted.
15. Complete the pre-deprecation gate below. Fix or roll back any failure; do
    not deprecate a source collection while a check is unresolved.

## Gate 1: Pre-Deprecation Approval

Both approvers must review this evidence and approve deprecation:

- [ ] The pre-migration inventory/export, Figma file version, repository
      revision, and passing CSS token audit are recorded.
- [ ] The new collection ID, mode IDs, and all 20 target variable IDs are
      mapped to both source variable IDs.
- [ ] All 20 `Light` and all 20 `Dark` values, aliases, scopes, descriptions,
      publishing settings, and exact `WEB` syntax have been compared and match.
- [ ] Fill, stroke, and text API smoke-test probes pass in both modes, with IDs,
      inspection results, and screenshots recorded.
- [ ] Every consumer ledger entry has been rebound and validated in both modes,
      with source and target IDs recorded.
- [ ] A complete post-rebind search or inspection reports zero unaccounted
      references to `UKIP/Color/Light` or `UKIP/Color/Dark`.
- [ ] Every mismatch or exception has a recorded disposition and owner.

| Pre-deprecation role | Name | Decision | Date | Evidence link |
| --- | --- | --- | --- | --- |
| Migration owner |  | Approve / Reject |  |  |
| Design-system reviewer |  | Approve / Reject |  |  |

If either decision is `Reject`, keep the Starter collections active and execute
the rollback procedure as needed.

## Deprecation Action

Only after both pre-deprecation decisions are `Approve`:

1. Record the current Figma file version and deprecation timestamp.
2. Mark `UKIP/Color/Light` and `UKIP/Color/Dark` deprecated in their
   descriptions and publishing guidance.
3. Do not delete or structurally modify either Starter collection.
4. Publish the approved library update and record the resulting version.

## Rollback

Retain `UKIP/Color/Light` and `UKIP/Color/Dark`, unchanged and publishable,
through pre-deprecation approval and post-deprecation verification. They are
the rollback source of truth.

If any target value, alias, scope, syntax, mode, or consumer binding fails:

1. Stop further mutations and keep the mutation freeze active.
2. Freeze the consumer ledger and record which entries are not started, rebound,
   validated, failed, or already restored. Record every affected component,
   component set, instance, style, node, property, source variable, target
   variable, collection, and mode ID.
3. For a partial migration, identify every consumer currently bound to
   `UKIP/Color`; do not assume the ledger status alone reflects the live file.
4. Restore every migrated or partially migrated consumer binding to the
   matching variable ID in
   `UKIP/Color/Light` or `UKIP/Color/Dark`.
5. Reapply the original explicit mode selection or collection usage recorded in
   the pre-migration inventory.
6. Validate every restored consumer in its original mode or collection context,
   and record the restoration result against its IDs in the consumer ledger.
7. Search or inspect the entire file and library to prove that no consumer
   remains bound to the incomplete target collection.
8. Remove or unpublish the incomplete `UKIP/Color` collection only after the
   preceding search is clean. Reactivate Starter publishing guidance if
   deprecation had already occurred. Do not delete the Starter collections.
9. Record the failure, restored bindings, affected IDs, operator, timestamp,
   screenshots, and follow-up owner. Obtain reviewer confirmation that rollback
   restored the pre-migration state before ending the freeze.

## Gate 2: Post-Deprecation Verification

After publishing the deprecation action:

- [ ] Reopen or refresh the published library and record the observed version.
- [ ] Confirm `UKIP/Color` remains published with `Light` and `Dark` modes and
      all 20 semantic variables available.
- [ ] Confirm both Starter collections are visibly deprecated but retained.
- [ ] Reinspect every consumer ledger entry and confirm it remains bound to the
      recorded `UKIP/Color` target variable ID.
- [ ] Validate every consumer again in both modes after publication.
- [ ] Repeat the full-file and library reference search and record zero
      unaccounted Starter references.
- [ ] Record the post-deprecation inventory/export, final Figma file version,
      consumer ledger, search result, screenshots, and any affected IDs.

## Final Sign-Off

End the mutation freeze only after post-deprecation verification is complete and
both final decisions are `Approve`.

| Final role | Name | Decision | Date | Evidence link |
| --- | --- | --- | --- | --- |
| Migration owner |  | Approve / Reject |  |  |
| Design-system reviewer |  | Approve / Reject |  |  |

If either final decision is `Reject`, keep the mutation freeze active, record
all affected IDs, and execute the rollback procedure.

After both final approvals, remove the disposable probes only after their IDs
and evidence are retained, announce completion, and end the mutation freeze.
