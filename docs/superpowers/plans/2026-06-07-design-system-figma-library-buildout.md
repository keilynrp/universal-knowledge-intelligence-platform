# UKIP Design System Figma Library Buildout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the governed UKIP Figma library from foundations through ten validated V1 components.

**Architecture:** Perform all Figma mutations sequentially with explicit phase and per-component checkpoints. Migrate Starter Light/Dark collections to a Professional multi-mode collection before component construction, then bind every component to approved semantic variables and validate with metadata plus screenshots.

**Tech Stack:** Figma Plugin API via MCP, Figma Variables, Auto Layout, component properties, Code Connect metadata. Spec: `docs/superpowers/specs/2026-06-07-design-system-figma-library-buildout-design.md`.

---

## Preconditions

- Figma Professional active for `Key's team`.
- File key: `noqJwfKV1ihlyfg9y65St7`.
- Foundation Governance and Component Contract plans completed.
- Current token audit exits 0.
- Load `figma-use` and `figma-generate-library` before every write.
- Never parallelize `use_figma` mutations.

---

## Persistent State

Create `docs/reference/figma/ukip-design-system-state.json`:

```json
{
  "runId": "ukip-ds-v1",
  "fileKey": "noqJwfKV1ihlyfg9y65St7",
  "phase": "professional-migration",
  "entities": {},
  "completedSteps": [],
  "pendingValidations": []
}
```

Update this ledger after every successful mutation using `apply_patch`; never
guess Figma IDs.

---

### Task 1: Inspect and back up the current Figma state

- [ ] Call `get_libraries`.
- [ ] Run read-only `use_figma` to return pages, collections, variables, styles,
  components, and code syntax.
- [ ] Save the reviewed inventory to
  `docs/reference/figma/ukip-design-system-pre-migration.json`.
- [ ] Verify counts: 37 primitives, 20 Light, 20 Dark, 18 dimensions.
- [ ] Commit:

```powershell
git add docs/reference/figma
git commit -m "docs: snapshot UKIP Figma foundation state"
```

---

### Task 2: Create the Professional color collection

- [ ] Create `UKIP/Color` with `Light` and `Dark` modes.
- [ ] For each approved semantic token, create one variable.
- [ ] Set Light and Dark values as aliases to `UKIP/Primitives`.
- [ ] Set explicit scopes.
- [ ] Set WEB syntax to the existing `var(--ukip-...)`.
- [ ] Return and persist every collection, mode, and variable ID.
- [ ] Validate with read-only metadata.
- [ ] Do not remove Starter collections.

**Checkpoint:** present the 20-token paired summary and await explicit approval.

---

### Task 3: Build styles and file structure

- [ ] Create ten approved Inter text styles from the Foundation spec.
- [ ] Create Panel, Soft, Violet Glow, and Cyan Glow effect styles.
- [ ] Create/rename pages:

```text
00 Cover
01 Getting Started
02 Foundations
---
10 Components
Button
Badge
Input
Select
PageHeader
StatCard
TabNav
EmptyState
ErrorBanner
Skeleton
---
90 Utilities
```

- [ ] Build visual foundation documentation for Light/Dark colors, typography,
  spacing, radii, and effects.
- [ ] Validate page metadata and screenshots.

**Checkpoint:** show page list and Foundations screenshots; await approval.

---

### Task 4: Build Button

- [ ] Read `docs/reference/components/Button.md`.
- [ ] Search local and subscribed libraries for Button patterns; reuse only if
  API and token model match.
- [ ] Build base component with Auto Layout and semantic bindings.
- [ ] Create approved axes: `Variant`, `Size`, `State`.
- [ ] Add text, booleans for left/right icon, and instance-swap icon properties.
- [ ] Arrange variants in a readable grid.
- [ ] Add source path and accessibility notes.
- [ ] Validate metadata, property definitions, bindings, and screenshot.
- [ ] Persist IDs.

**Checkpoint:** await explicit Button approval.

---

### Task 5: Build Badge, Input, and Select

Execute one component at a time, each with its own approval:

1. Read its contract file.
2. Search available design-system assets.
3. Create the dedicated page content.
4. Build base component.
5. Bind all approved variables.
6. Add variant/component properties.
7. Validate metadata and screenshot.
8. Persist IDs and checkpoint.

Do not start the next component until the current component is approved.

---

### Task 6: Build composed V1 components

Repeat the same per-component sequence for:

- PageHeader
- StatCard
- TabNav
- EmptyState
- ErrorBanner
- Skeleton

Use slots/text properties to avoid variant explosion. Keep product-specific
content out of the library examples.

---

### Task 7: Integration and QA

- [ ] Add Code Connect metadata/mappings where supported.
- [ ] Audit for hardcoded fills, strokes, radii, and spacing.
- [ ] Audit duplicate/unnamed nodes.
- [ ] Check text contrast and focus indicators.
- [ ] Check minimum interactive target sizes.
- [ ] Capture screenshots of every page.
- [ ] Mark Starter collections deprecated only after all components bind to
  `UKIP/Color`.
- [ ] Update the state ledger and changelog.

**Final checkpoint:** present the QA report and request library sign-off.

---

### Task 8: Final verification

Required evidence:

- One `UKIP/Color` collection with Light/Dark modes.
- 20 semantic variables with correct aliases and WEB syntax.
- All planned pages present.
- Ten V1 component pages validated.
- No unresolved hardcoded visual properties except documented exceptions.
- State ledger contains all collection/page/component IDs.
- Design-system changelog records the Figma V1 build.
