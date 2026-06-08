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
- [ ] Existing component and style consumers of both Starter collections are
      inventoried so their bindings can be checked and restored if necessary.
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
9. Create a disposable probe frame that is not a library component. Add
   independently inspectable probe layers for:
   - fill bindings;
   - stroke bindings;
   - text fill bindings.
10. Bind every target variable to each applicable probe property. Use separate
    probe layers where a variable's scope does not permit all three properties;
    never broaden a scope merely to make a probe pass.
11. Switch the probe frame between `Light` and `Dark`. Confirm each property
    remains bound to the same target variable ID and resolves to the expected
    mode value. Record inspection evidence and screenshots for both modes.
12. Rebind an inventoried sample of existing styles, components, instances, and
    direct node consumers to `UKIP/Color`. Validate both modes and record all
    affected IDs. Expand validation to every consumer if any sample fails.
13. Run the verification checklist below. Fix or roll back any failure; do not
    deprecate a source collection while a check is unresolved.
14. After reviewer sign-off, mark `UKIP/Color/Light` and `UKIP/Color/Dark`
    deprecated in their descriptions and publishing guidance. Do not delete
    them during this migration.
15. Remove the disposable probe frame only after its IDs, screenshots, and
    inspection results have been recorded. End the mutation freeze and announce
    completion.

## Rollback

Retain `UKIP/Color/Light` and `UKIP/Color/Dark`, unchanged and publishable,
until all value, probe, consumer, and reviewer validation passes. They are the
rollback source of truth.

If any target value, alias, scope, syntax, mode, or consumer binding fails:

1. Stop further mutations and keep the mutation freeze active.
2. Record the failing target variable IDs and every affected node, style,
   component, instance, collection, and mode ID.
3. Restore affected bindings to the matching variable ID in
   `UKIP/Color/Light` or `UKIP/Color/Dark`.
4. Reapply the original explicit mode selection or collection usage recorded in
   the pre-migration inventory.
5. Verify restored fill, stroke, and text behavior in the affected theme.
6. Remove or unpublish the incomplete `UKIP/Color` collection only after no
   consumers remain bound to it. Do not alter or delete the Starter collections.
7. Record the failure, restored bindings, affected IDs, operator, timestamp,
   screenshots, and follow-up owner. Obtain reviewer confirmation that rollback
   restored the pre-migration state before ending the freeze.

## Verification Evidence

- [ ] Pre-migration inventory/export location and timestamp are recorded.
- [ ] Figma file version and repository revision are recorded.
- [ ] CSS token audit command and passing output are attached.
- [ ] New collection ID and `Light` and `Dark` mode IDs are recorded.
- [ ] All 20 target variable IDs are mapped to both source variable IDs.
- [ ] Names, aliases, scopes, descriptions, publishing settings, and exact
      `WEB` syntax match the source inventory and checklist.
- [ ] A comparison artifact proves 20 of 20 `Light` values and 20 of 20 `Dark`
      values match their respective Starter collection values.
- [ ] Disposable fill, stroke, and text probe IDs are recorded.
- [ ] Probe screenshots and variable inspection evidence are attached for both
      modes.
- [ ] Consumer validation lists checked style, component, instance, and node
      IDs, with no unresolved or detached bindings.
- [ ] `UKIP/Color/Light` and `UKIP/Color/Dark` remained available through
      validation and were only deprecated after approval.
- [ ] Any mismatch, rollback, or exception includes affected IDs, disposition,
      and owner.
- [ ] Post-migration inventory/export and final Figma file version are recorded.

## Sign-Off Checkpoint

Deprecation is blocked until both approvers explicitly sign off on the evidence.

| Role | Name | Decision | Date | Evidence link |
| --- | --- | --- | --- | --- |
| Migration owner |  | Approve / Reject |  |  |
| Design-system reviewer |  | Approve / Reject |  |  |

Final decision:

- [ ] Approved: all checks pass; deprecate the Starter collections without
      deleting them.
- [ ] Rejected: execute or retain rollback, document affected IDs, and schedule
      a corrected migration under a new mutation freeze.
