# UKIP Design System — Figma Library Buildout Design

**Date:** 2026-06-07
**Status:** Draft for iterative review
**Related:** Foundation Governance, Component Contract Alignment, Documentation & Maintenance
**Figma file:** `https://www.figma.com/design/noqJwfKV1ihlyfg9y65St7`

---

## 1. Problem & Goal

The UKIP Figma file currently contains foundation variables, but not yet the
documented pages, styles, or component library needed for everyday design work.
The current Figma Starter plan also limits variable modes and MCP calls, so the
buildout must be staged carefully.

**Goal:** define a stepwise Figma library buildout that moves from foundations to
documented, token-bound components without duplicating work or breaking future
Professional migration.

### Non-goals

- No one-shot generation of the whole library.
- No dependence on Material or Simple Design System as the primary source.
- No building components before their contracts are approved.

---

## 2. Current Figma State

File: `UKIP Design System`

Existing:

- `UKIP/Primitives`
- `UKIP/Color/Light`
- `UKIP/Color/Dark`
- `UKIP/Dimensions`

Blocked on Starter plan:

- multi-mode `UKIP/Color` collection;
- sustained MCP buildout after the tool-call limit is reached.

---

## 3. Target File Structure

Pages:

1. `00 Cover`
2. `01 Getting Started`
3. `02 Foundations`
4. `---`
5. `10 Components`
6. `Button`
7. `Badge`
8. `Input`
9. `Select`
10. `PageHeader`
11. `StatCard`
12. `TabNav`
13. `EmptyState`
14. `ErrorBanner`
15. `Skeleton`
16. `---`
17. `90 Utilities`

Each component page includes:

- title and description;
- React source path;
- props-to-variant mapping;
- variant grid;
- state examples;
- accessibility notes;
- implementation checklist.

---

## 4. Build Phases

### Phase 1 — Foundations

Status: partially complete.

Completed:

- variables created in Starter-compatible collections.

Remaining:

- text styles;
- effect styles;
- visual documentation for colors, type, spacing, radius, shadows;
- Getting Started page.

### Phase 2 — Professional Migration

Once Professional is available:

1. Create `UKIP/Color` with `Light` and `Dark` modes.
2. Recreate or migrate semantic variables preserving names and code syntax.
3. Verify values against CSS.
4. Rebind future components to the merged collection.
5. Deprecate `UKIP/Color/Light` and `UKIP/Color/Dark` after validation.

### Phase 3 — Component Pages

Build one component at a time:

1. inspect approved component contract;
2. create page;
3. build base component with Auto Layout;
4. bind visual properties to variables;
5. create variants;
6. add component properties;
7. add documentation;
8. validate metadata and screenshot;
9. request checkpoint approval.

### Phase 4 — Integration

- Add Code Connect mappings where useful.
- Audit hardcoded fills/strokes.
- Audit naming and duplicate nodes.
- Capture page screenshots.
- Prepare library publication checklist.

---

## 5. Design Decisions

### A. Build From UKIP, Not External Kits

External libraries can be inspected for patterns, but UKIP components should be
owned locally because the React implementation is custom.

### B. Bind Tokens By Default

Fills, strokes, radii, spacing, and focus indicators should bind to variables
unless a fixed value is intentional and documented.

### C. Avoid Variant Explosion

Use instance-swap or boolean properties for optional icons and content. Keep
variant axes limited to public API and state.

### D. Checkpoint Every Component

No batching across components. Each component requires visual and structural
approval before moving to the next.

---

## 6. Implementation Slices

### Slice 1 — Starter-Safe Documentation Prep

- Continue local documentation while MCP is limited.
- Prepare exact scripts/steps for Professional migration.
- Do not create more Figma content until rate limits reset or plan changes.

### Slice 2 — Foundations Visual Pages

- Create Cover.
- Create Getting Started.
- Create Foundations swatches and type specimens.
- Validate screenshots.

### Slice 3 — First Component: Button

- Use approved Button contract.
- Build token-bound variants.
- Validate states and accessibility.

### Slice 4 — Form Primitives

- Build `Badge`, `Input`, and `Select`.
- Reuse Button patterns for states and documentation.

### Slice 5 — Composed Components

- Build PageHeader, StatCard, TabNav, EmptyState, ErrorBanner, Skeleton.

---

## 7. Validation

For each Figma phase:

- inspect page/component metadata;
- capture screenshot;
- verify variable bindings;
- verify variant names and property names;
- compare with React contract;
- record checkpoint outcome.

For Professional migration:

- verify mode values match prior Light/Dark collections;
- verify CSS code syntax;
- verify no duplicate or orphaned semantic names;
- verify future component binding target is `UKIP/Color`.

---

## 8. Risks

| Risk | Mitigation |
| --- | --- |
| MCP rate limits interrupt work | Keep state documented; proceed in small checkpoints |
| Professional migration breaks bindings | Migrate before component buildout where possible |
| Components drift from React | Require contract approval before Figma work |
| Visual docs become decorative only | Include source paths, code syntax, and usage rules |

---

## 9. Acceptance Criteria

- Figma page structure matches this spec.
- Foundations are visually documented.
- Components are created one at a time with checkpoint approvals.
- The library can migrate to Professional modes without renaming semantic tokens.
- Figma is useful for implementation, not just presentation.
