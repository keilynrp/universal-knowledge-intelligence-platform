# UKIP Design System — Component Contract Alignment Design

**Date:** 2026-06-07
**Status:** Draft for iterative review
**Related:** Foundation Governance, Documentation & Maintenance, Figma Library Buildout
**Depends on:** `2026-06-07-design-system-foundation-governance-design.md`

---

## 1. Problem & Goal

UKIP has reusable React UI components, but their visual contracts are not yet
fully governed across Figma and implementation. Some components use `--ukip-*`
tokens; others still rely on hardcoded Tailwind color families. If Figma
components are built without matching React prop APIs, the design library becomes
decorative instead of implementable.

**Goal:** define a component contract model that aligns React props, Figma
variants, states, accessibility behavior, token usage, and tests for the V1
component set.

### Non-goals

- No one-shot refactor of all UI components.
- No visual redesign outside the established UKIP language.
- No fragile screenshot snapshots as the primary contract.

---

## 2. V1 Component Scope

Dependency order:

1. `Button`
2. `Badge`
3. `Input`
4. `Select`
5. `PageHeader`
6. `StatCard`
7. `TabNav`
8. `EmptyState`
9. `ErrorBanner`
10. `Skeleton`

This order starts with small primitives, then moves to composed display and
state components.

---

## 3. Contract Model

Each component gets a contract with:

| Area | Required content |
| --- | --- |
| React API | props, defaults, allowed values |
| Figma API | variants, component properties, slots |
| Tokens | semantic variables used |
| States | default, hover, focus, disabled, loading, error as applicable |
| Accessibility | roles, labels, keyboard behavior, contrast, hit area |
| Tests | behavior/API assertions |
| Migration notes | hardcoded values replaced or deferred |

### A. React-to-Figma Mapping

React props become Figma variant axes only when they materially change the visual
surface.

Examples:

- `Button.variant` -> Figma `Variant`
- `Button.size` -> Figma `Size`
- `Button.leftIcon/rightIcon` -> Figma boolean or instance-swap properties
- `Input.error` -> Figma `State=Error`

Do not create a variant for arbitrary content. Use text properties or slots.

### B. State Policy

Required states by component type:

| Component type | Required states |
| --- | --- |
| Action | default, hover, focus, disabled |
| Form | default, focus, disabled, error |
| Feedback | default plus severity |
| Layout/display | default, empty/loading where relevant |

Focus visibility must remain tokenized through `--ukip-focus-ring` or its Figma
semantic equivalent.

### C. Token Usage Policy

Component styling should prefer semantic tokens:

- surface/background
- text/default or text/strong
- border/default
- action/primary
- status/success, warning, danger
- spacing and radius dimensions

Tailwind utility classes remain acceptable for layout and responsive behavior.
Hardcoded colors should be replaced or explicitly deferred.

---

## 4. Component-Specific Initial Contracts

### Button

React API:

- `variant`: `primary | secondary | ghost | outline | danger`
- `size`: `sm | md | lg | icon`
- `leftIcon`, `rightIcon`
- native button props

Figma axes:

- `Variant`
- `Size`
- `State`
- `Icon left`
- `Icon right`

### Badge

React API:

- `variant`: `default | success | warning | error | info | purple`
- `size`: `sm | md`
- `dot`
- `dotPulse`

Figma axes:

- `Variant`
- `Size`
- `Dot`
- `Pulse` only if animation is represented as documentation, not a static visual
  promise.

### Input and Select

React API:

- native input/select props
- `label`
- `hint`
- `error`

Figma axes:

- `State`: default, focus, disabled, error
- `Label`: true/false
- `Hint`: true/false

### PageHeader, StatCard, TabNav

These are composed components. Their Figma components should expose text
properties and slots while minimizing variant explosion.

### EmptyState, ErrorBanner, Skeleton

These document feedback and loading patterns. Their contracts must clarify when
to use each component and how severity/loading semantics map to accessible text.

---

## 5. Implementation Slices

### Slice 1 — Contract Inventory

- Read each component file.
- Document current props and visual decisions.
- Identify token gaps.

### Slice 2 — Tests Before Refactors

- Add focused tests for props and accessible output.
- Verify tests fail only when they encode new behavior.
- Avoid snapshot-only contracts.

### Slice 3 — Tokenized Refactors

- Replace hardcoded visual values where an existing token applies.
- Keep class changes scoped per component.
- Do not alter data flow or product behavior.

### Slice 4 — Figma Component Build

- Build each component only after its contract is reviewed.
- Validate screenshots and metadata per component.
- Move to the next component only after checkpoint approval.

---

## 6. Validation

Per component:

- React tests pass.
- Figma variant count matches the approved contract.
- Visual properties bind to semantic variables.
- Accessibility checks pass for contrast, focus, role, and target size.
- Documentation includes usage guidance and migration notes.

---

## 7. Risks

| Risk | Mitigation |
| --- | --- |
| Variant explosion | Use slots and boolean properties instead of cross-product variants |
| Figma API differs from React API | Treat React props as the implementation contract |
| Tests become brittle | Prefer semantic DOM assertions over screenshots |
| Hardcoded values require new tokens | Defer and record instead of inventing tokens mid-refactor |

---

## 8. Acceptance Criteria

- Each V1 component has an explicit contract.
- `Button`, `Badge`, `Input`, and `Select` establish reusable patterns.
- Figma variants map cleanly to React props.
- Component buildout can proceed one checkpoint at a time.

