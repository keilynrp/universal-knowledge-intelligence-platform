# UKIP Design System — Foundation Governance Design

**Date:** 2026-06-07
**Status:** Draft for iterative review
**Related:** `docs/reference/UKIP_DESIGN_SYSTEM.md`, `frontend/app/styles/tokens.css`
**Depends on:** Current UKIP foundation variables in Figma Starter file
**Governs:** Component Contract Alignment, Documentation & Maintenance, Figma Library Buildout

---

## 1. Problem & Goal

UKIP now has the beginning of a shared design foundation: CSS tokens in code and
95 matching Figma variables in the `UKIP Design System` file. Without governance,
that foundation can drift quickly: designers may introduce new visual values in
Figma, engineers may hardcode Tailwind colors in React, and Light/Dark behavior
may diverge.

**Goal:** establish a durable governance model for design foundations so tokens,
themes, naming, ownership, review gates, and Figma Professional migration are
coherent before component buildout scales.

### Non-goals

- No component refactor in this spec. Component work belongs to the Component
  Contract Alignment spec.
- No automated token sync pipeline yet. This spec defines the contract; tooling
  can follow once the contract survives review.
- No brand redesign. The existing UKIP visual language remains the baseline.

---

## 2. Current State

Technical source:

- `frontend/app/styles/tokens.css`
- `frontend/app/globals.css`
- `frontend/app/styles/globals.css`

Figma source:

- `UKIP Design System`: `https://www.figma.com/design/noqJwfKV1ihlyfg9y65St7`
- Current plan: Starter
- Limitation: one mode per variable collection

Current Figma inventory:

| Collection | Count | Notes |
| --- | ---: | --- |
| `UKIP/Primitives` | 37 | Raw color values |
| `UKIP/Color/Light` | 20 | Light semantic aliases |
| `UKIP/Color/Dark` | 20 | Dark semantic aliases |
| `UKIP/Dimensions` | 18 | Spacing, radii, control and icon sizes |

Current code inventory:

- Light and Dark CSS custom properties.
- Additive dimension tokens for spacing, radius, control, and icon sizing.
- Some UI components already use `--ukip-*`; others still include Tailwind
  hardcoded colors.

---

## 3. Governance Decisions

### A. Authority Model

Code is the **technical authority** until the Figma library is mature. Figma is
the **visual contract**. A value is production-ready only when both surfaces can
name it consistently.

If Figma and code disagree:

1. record the discrepancy;
2. choose whether design or implementation wins;
3. update both surfaces when possible;
4. avoid preserving untracked hardcoded values.

### B. Token Classes

Use four foundation classes:

| Class | Purpose | Example |
| --- | --- | --- |
| Primitive | raw palette/dimension value | `violet/600` |
| Semantic | user-facing design role | `color/action/primary` |
| Component | component-specific semantic, only when needed | `button/primary/background` |
| Utility | layout or helper token | `spacing/4` |

V1 should prefer semantic tokens over component tokens. Component tokens are
allowed only when repeated component-specific decisions cannot be expressed with
global semantics.

### C. Naming

Figma variables use slash-separated names:

- `color/background/default`
- `color/text/strong`
- `spacing/4`
- `radius/md`

CSS variables use `--ukip-*`:

- `--ukip-bg`
- `--ukip-text-strong`
- `--ukip-space-4`
- `--ukip-radius-md`

Every Figma variable that maps to code must set WEB code syntax as
`var(--ukip-...)`.

### D. Theme Modes

Starter constraint:

- keep `UKIP/Color/Light` and `UKIP/Color/Dark` separate;
- maintain identical semantic variable names across both collections.

Professional target:

- merge into one `UKIP/Color` collection;
- modes: `Light`, `Dark`;
- preserve variable names and CSS code syntax;
- validate all component bindings after merge.

### E. Token Change Policy

Token changes are classified:

| Change | Examples | Required review |
| --- | --- | --- |
| Additive | new semantic token | design + frontend |
| Value update | `--ukip-primary` hue change | visual QA + contrast |
| Rename | `color/action/primary` rename | migration note |
| Removal | deleting unused token | usage search + deprecation |

Renames and removals require a migration path. Additive changes must explain why
an existing semantic token was not enough.

---

## 4. Deliverables

1. Updated design-system reference doc with authority and token policy.
2. Token inventory table covering CSS and Figma names.
3. Migration note for Figma Professional mode consolidation.
4. Review checklist for new or changed tokens.
5. Drift audit procedure for hardcoded values.

---

## 5. Implementation Slices

### Slice 1 — Foundation Reference Hardening

- Expand `docs/reference/UKIP_DESIGN_SYSTEM.md`.
- Add a token inventory section.
- Mark Figma Starter limitations and Professional target.

### Slice 2 — Token Usage Audit

- Search `frontend/app/components/ui/` for hardcoded Tailwind colors and radii.
- Categorize each as acceptable, replaceable with existing token, or requiring a
  new semantic token.
- Produce a short gap list before code changes.

### Slice 3 — Professional Migration Plan

- Define exact collection merge steps.
- Define validation after merge.
- Keep fallback plan: if merge cannot preserve bindings, rebuild affected
  component bindings explicitly.

---

## 6. Validation

Required checks:

- CSS token declarations have no accidental duplicates.
- Every documented CSS token exists in `tokens.css`.
- Every Figma semantic token has matching CSS code syntax.
- Light and Dark semantic names remain paired.
- Contrast is checked for text/action/status tokens before component use.

---

## 7. Risks

| Risk | Mitigation |
| --- | --- |
| Figma Starter limitations force temporary duplication | Keep Light/Dark names identical and document Professional merge |
| Token sprawl | Require semantic justification before adding tokens |
| Hardcoded visual values persist in components | Run component usage audit before refactors |
| Design/code authority conflict | Use explicit discrepancy records and review decision |

---

## 8. Acceptance Criteria

- Governance rules are documented and referenced by the other three specs.
- Foundation token names are stable enough for component buildout.
- Figma Professional migration has a clear path.
- Component specs can rely on this document for source-of-truth decisions.

