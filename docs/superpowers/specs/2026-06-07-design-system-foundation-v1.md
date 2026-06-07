# UKIP Design System Foundation v1

## Status

Implementation-ready, incremental foundation.

## Problem

UKIP has governed visual tokens and a growing UI component folder, but product
surfaces still implement controls and semantic colors independently. This
creates avoidable UX drift, inconsistent accessibility, duplicated state
styling, and high review cost across academic and enterprise deployments.

## Product Requirements

1. Preserve the current UKIP identity: violet for brand, cyan for intelligence,
   emerald for evidence/success, amber for review, and red for risk.
2. Preserve light-first behavior and the existing opt-in dark theme.
3. Provide fully functional, keyboard-accessible action and form primitives.
4. Maintain backwards compatibility for existing `Button`, `IconButton`,
   `Input`, and `Select` callers.
5. Make error, hint, required, disabled, loading, and focus states consistent.
6. Use semantic tokens instead of raw palette values inside governed primitives.
7. Establish an adoption path that can be delivered surface by surface.

## Scope

### Included

- Semantic control and feedback tokens.
- Button and icon-button state contract.
- Input, select, textarea, checkbox, radio, and switch primitives.
- Accessible label, description, error, loading, and focus behavior.
- Unit tests for behavior and accessibility contracts.
- A regression baseline that prevents new raw controls and palette debt.
- Documentation and roadmap updates.

### Excluded

- Whole-product component migration.
- Visual redesign of existing product surfaces.
- Dialog, menu, tabs, data table, and chart contracts.
- Storybook and visual regression infrastructure.

## UX Contract

- Interactive controls have a minimum 44px target for default and icon sizes.
- Focus is visible and uses the UKIP focus token.
- Errors use `aria-invalid`, `aria-describedby`, and `role="alert"`.
- Loading actions expose `aria-busy` and cannot be submitted twice.
- Switches use native button keyboard behavior with `role="switch"`.
- Reduced-motion preferences shorten nonessential transitions.

## Adoption Lifecycle

1. Foundation contract and regression baseline.
2. Home and global navigation migration.
3. Entity, authority, import, and settings workflows.
4. Analytics and dashboard surfaces.
5. Storybook, visual regression, and automated accessibility gates.

## Acceptance Criteria

- Frontend typecheck, lint, and unit tests pass.
- New primitives are exported from the UI barrel.
- Existing component APIs remain valid.
- Governance checks cannot increase raw-control or raw-palette debt.
- No user-facing branding regression is introduced.
