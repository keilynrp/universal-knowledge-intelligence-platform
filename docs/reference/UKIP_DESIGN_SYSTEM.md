# UKIP Design System

## Purpose

The UKIP Design System keeps product design and frontend implementation aligned
through shared naming, traceable tokens, and matching component APIs.

- Figma file: [UKIP Design System](https://www.figma.com/design/noqJwfKV1ihlyfg9y65St7)
- Technical source: `frontend/app/styles/tokens.css`
- Component source: `frontend/app/components/ui/`
- Initial version: V1

## Source Of Truth

Code is the technical source of truth while the Figma library is being
established. A design change is implementation-ready only after its token or
component API has an equivalent in code.

When Figma and code differ:

1. Record the discrepancy.
2. Decide whether the design or implementation should change.
3. Update both surfaces in the same delivery when possible.
4. Avoid adding an untracked hardcoded value to either surface.

## Foundation Architecture

The Starter plan permits one mode per variable collection. The current Figma
file therefore uses these collections:

| Collection | Purpose |
| --- | --- |
| `UKIP/Primitives` | Raw palette values hidden from normal property pickers |
| `UKIP/Color/Light` | Light semantic color aliases |
| `UKIP/Color/Dark` | Dark semantic color aliases |
| `UKIP/Dimensions` | Spacing, radius, control, and icon dimensions |

Current inventory:

- 37 primitive color variables
- 20 Light semantic variables
- 20 Dark semantic variables
- 18 dimension variables
- 95 variables total

On Figma Professional, merge `UKIP/Color/Light` and `UKIP/Color/Dark` into one
`UKIP/Color` collection with `Light` and `Dark` modes. Preserve semantic names
and CSS code syntax so component bindings remain stable.

## Token Classes

UKIP uses four token classes:

| Class | Purpose | Example |
| --- | --- | --- |
| Primitive | Raw palette or dimension value; not a product-facing decision | `violet/600` |
| Semantic | A reusable design role shared across products and components | `color/action/primary` |
| Component | A component-specific role used only when global semantics cannot express a repeated decision | `button/primary/background` |
| Utility | A reusable layout or helper value | `spacing/4` |

V1 prefers semantic tokens. Component tokens require evidence that the decision
is both repeated and component-specific; they must not become aliases for an
existing semantic token. Product-specific and data-visualization colors remain
local unless repeated use establishes a cross-product semantic role.

## Token Mapping

Semantic Figma variables map directly to CSS custom properties:

| Figma variable | CSS |
| --- | --- |
| `color/background/default` | `var(--ukip-bg)` |
| `color/panel/default` | `var(--ukip-panel)` |
| `color/border/default` | `var(--ukip-border)` |
| `color/text/default` | `var(--ukip-text)` |
| `color/text/strong` | `var(--ukip-text-strong)` |
| `color/action/primary` | `var(--ukip-primary)` |
| `color/status/danger` | `var(--ukip-danger)` |
| `color/focus/ring` | `var(--ukip-focus-ring)` |

Dimensions use the same convention:

These CSS dimension tokens are present in the current approved worktree and are
pending the baseline token commit. This note preserves provenance for readers
reviewing this documentation commit in isolation.

| Figma variable | CSS |
| --- | --- |
| `spacing/4` | `var(--ukip-space-4)` |
| `radius/md` | `var(--ukip-radius-md)` |
| `radius/full` | `var(--ukip-radius-full)` |
| `size/control/md` | `var(--ukip-control-md)` |
| `size/icon/md` | `var(--ukip-icon-md)` |

## Token Change Review

Every token change must identify its class, affected Light and Dark behavior,
and corresponding Figma variable and CSS custom property when both apply.

| Change | Required evidence |
| --- | --- |
| Add | Semantic use case; search showing existing tokens are insufficient; proposed name, class, Light/Dark values, contrast or accessibility checks, and affected Figma/CSS mappings |
| Value | Before/after visual examples; affected usage inventory; Light/Dark review; contrast or accessibility results; approval from design and frontend owners |
| Rename | Usage search across code and Figma; old-to-new mapping; migration notes; compatibility or coordinated rollout plan; validation that component bindings remain intact |
| Remove | Usage search proving no unsupported consumers; deprecation and migration record; replacement where applicable; confirmation that Figma bindings and CSS references are cleared |

Additions and value changes require design and frontend review. Renames and
removals are breaking changes unless a compatibility path or coordinated
migration is documented.

## Drift Audit

Run the design-token audit from the repository root:

```bash
cd frontend && npm run audit:design-tokens
```

Review results against
[`UKIP_DESIGN_SYSTEM_TOKEN_AUDIT.md`](UKIP_DESIGN_SYSTEM_TOKEN_AUDIT.md), which
records the baseline, disposition rules, and reviewed findings. Audit output is
evidence for review, not an automatic replacement list. Do not blindly replace
product-specific, KPI, illustration, or data-visualization colors with global
tokens; first decide whether each color is intentional local meaning,
replaceable drift, or evidence for a new reusable semantic token.

## V1 Component Scope

The Figma component library will be built and aligned with the existing React
components in dependency order:

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

Each Figma component must:

- use Auto Layout;
- bind visual properties to semantic variables;
- expose variants matching the React prop API;
- include default, hover, focus, disabled, and error states where applicable;
- document usage and accessibility requirements;
- be checked against its frontend implementation before approval.

## Planned Figma Structure

1. `00 Cover`
2. `01 Getting Started`
3. `02 Foundations`
4. `---`
5. `10 Components`
6. One page per component
7. `---`
8. `90 Utilities`

## Maintenance Workflow

For each design-system change:

1. Start from a semantic use case, not a raw visual value.
2. Reuse an existing token or propose a named token.
3. Keep Figma variable names and CSS code syntax aligned.
4. Keep Figma variants and React props aligned.
5. Review Light and Dark behavior.
6. Check contrast, focus visibility, and minimum target size.
7. Apply the Token Change Review evidence requirements.
8. Run the drift audit and review findings by disposition.
9. Record breaking changes and migration notes.

## Definition Of Done

A foundation or component is complete when:

- Figma and code use matching semantics;
- no unexplained hardcoded visual values remain;
- Light and Dark behavior is documented;
- component states and accessibility behavior are covered;
- token changes include the required review evidence;
- drift audit findings are reviewed and intentionally dispositioned;
- the implementation passes its existing lint and test checks.
