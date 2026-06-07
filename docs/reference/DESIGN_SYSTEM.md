# UKIP Design System

## Purpose

The UKIP Design System is the governed contract for product identity,
interaction behavior, accessibility, and reusable UI implementation. It is not
only a visual library: it defines how product surfaces remain consistent across
domains, languages, themes, and stakeholder deployments.

## Foundations

- **Brand:** violet identifies UKIP and primary product actions.
- **Intelligence:** cyan identifies AI-assisted or enrichment behavior.
- **Evidence:** emerald identifies confirmed, resolved, or evidence-backed state.
- **Review:** amber identifies pending, uncertain, or review-required state.
- **Risk:** red identifies failures, destructive actions, and governance violations.
- **Theme:** light is the default; dark is an explicit user choice.
- **Typography:** Geist is the interface family; metrics use tabular figures.
- **Density:** analytical surfaces may be dense, but default interactive targets
  remain at least 44px.

The source of truth for token values is
`frontend/app/styles/tokens.css`. Component-level CSS contracts live in
`frontend/app/styles/globals.css`.

## Component Contract

Use components exported from `frontend/app/components/ui` for shared actions,
form controls, feedback, navigation, metrics, and surfaces.

### Actions

- `Button`: primary, secondary, ghost, outline, and danger variants.
- `IconButton`: requires an accessible `label`.
- Loading actions use `loading` and optionally `loadingLabel`.

### Forms

- `Input`, `Select`, and `Textarea` own label, hint, and error relationships.
- `Checkbox` and `Radio` provide a single label/control hit target.
- `Switch` is reserved for immediate boolean settings.
- Submit-time errors must be actionable and rendered adjacent to their field.

## Engineering Rules

1. Do not introduce raw `<button>`, `<input>`, `<select>`, or `<textarea>`
   elements when a governed primitive satisfies the requirement.
2. Do not use palette colors to encode product semantics. Use `--ukip-*`
   semantic tokens.
3. Product-specific composition belongs outside `components/ui`.
4. New variants require a documented semantic purpose and tests.
5. Accessibility behavior is part of the API contract, not optional decoration.
6. Migrations must preserve behavior and branding before removing legacy styles.

## Exceptions

Raw controls are permitted for specialized browser APIs, graph/canvas
interactions, file inputs, and cases where the native element is itself the
intended experience. Exceptions must remain accessible and should be documented
in the owning module.

## Delivery Model

Adoption proceeds through small, reviewable PRDs/specs:

1. Define the component or pattern contract.
2. Implement primitives and tests.
3. Migrate one representative product surface.
4. Validate light/dark, EN/ES, keyboard, and responsive behavior.
5. Expand migration while reducing the governance baseline.
