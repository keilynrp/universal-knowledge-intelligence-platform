# UKIP Design System Documentation & Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a lightweight, versioned contribution and release workflow for UKIP design-system changes.

**Architecture:** Keep the reference document concise, place reusable contribution templates in `docs/reference/components`, and record releases in a dedicated changelog. A documentation test verifies required headings and links without introducing a documentation framework.

**Tech Stack:** Markdown, Node.js, Vitest. Spec: `docs/superpowers/specs/2026-06-07-design-system-documentation-maintenance-design.md`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `docs/reference/UKIP_DESIGN_SYSTEM.md` | Entry point and workflow |
| `docs/reference/UKIP_DESIGN_SYSTEM_CHANGELOG.md` | Version and status history |
| `docs/reference/components/COMPONENT_TEMPLATE.md` | Repeatable component documentation |
| `docs/reference/DESIGN_SYSTEM_CHANGE_TEMPLATE.md` | Token/component proposal template |
| `frontend/__tests__/designSystemDocs.test.ts` | Required-document contract |

---

### Task 1: Add the documentation contract test

**Files:**
- Create: `frontend/__tests__/designSystemDocs.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { readFile } from "node:fs/promises";
import path from "node:path";
import { describe, expect, it } from "vitest";

const repo = path.resolve(process.cwd(), "..");

describe("design-system documentation", () => {
  it("contains governance, contribution, versioning, and changelog surfaces", async () => {
    const reference = await readFile(
      path.join(repo, "docs/reference/UKIP_DESIGN_SYSTEM.md"),
      "utf8",
    );
    const changelog = await readFile(
      path.join(repo, "docs/reference/UKIP_DESIGN_SYSTEM_CHANGELOG.md"),
      "utf8",
    );
    expect(reference).toContain("## Change Workflow");
    expect(reference).toContain("## Versioning");
    expect(changelog).toContain("## Unreleased");
  });
});
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
npx vitest run __tests__/designSystemDocs.test.ts
```

Expected: FAIL because the changelog and headings are missing.

---

### Task 2: Expand the reference workflow

**Files:**
- Modify: `docs/reference/UKIP_DESIGN_SYSTEM.md`

- [ ] Add exact sections:

```markdown
## Change Workflow
### New Token
### Component Change
### Figma-Only Exploration

## Versioning
Patch, Minor, Major, and V1 readiness rules.

## Ownership
Role-based owners for tokens, CSS, Figma, accessibility, and release notes.

## Review Checklists
Foundation, component, and documentation checklists.
```

- [ ] Run the test again.

Expected: still FAIL only because the changelog is absent.

---

### Task 3: Add templates and changelog

**Files:**
- Create: `docs/reference/UKIP_DESIGN_SYSTEM_CHANGELOG.md`
- Create: `docs/reference/components/COMPONENT_TEMPLATE.md`
- Create: `docs/reference/DESIGN_SYSTEM_CHANGE_TEMPLATE.md`

- [ ] **Step 1: Create changelog**

Use:

```markdown
# UKIP Design System Changelog

## Unreleased

### Added
- Foundation governance and implementation plans.

## 0.1.0-draft — 2026-06-07

### Added
- 95 Figma foundation variables.
- CSS dimension tokens.
- Initial design-system reference and four approved design specs.
```

- [ ] **Step 2: Create component template**

Include required headings from the component-contract plan plus reviewer
checkboxes.

- [ ] **Step 3: Create change proposal template**

Include:

```markdown
# Design System Change
## Problem
## Proposed Semantic Change
## Existing Alternatives Reviewed
## Code Impact
## Figma Impact
## Light/Dark
## Accessibility
## Migration
## Validation
## Status
```

- [ ] **Step 4: Verify GREEN**

```powershell
npx vitest run __tests__/designSystemDocs.test.ts
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add docs/reference frontend/__tests__/designSystemDocs.test.ts
git commit -m "docs: establish design system maintenance workflow"
```

---

### Task 4: Exercise the workflow on Button

**Files:**
- Modify: `docs/reference/components/Button.md`
- Modify: `docs/reference/UKIP_DESIGN_SYSTEM_CHANGELOG.md`

- [ ] Record the actual Button contract status:

```markdown
## Status
- Contract: implemented
- React tests: passing
- Figma component: pending Professional buildout
```

- [ ] Add an Unreleased changelog entry for the Button contract.

- [ ] Verify:

```powershell
npx vitest run __tests__/designSystemDocs.test.ts __tests__/ui.Button.test.tsx
```

- [ ] Commit:

```powershell
git add docs/reference/components/Button.md docs/reference/UKIP_DESIGN_SYSTEM_CHANGELOG.md
git commit -m "docs: exercise design system workflow on Button"
```

---

### Task 5: Final verification

Run:

```powershell
cd frontend
npx vitest run __tests__/designSystemDocs.test.ts
cd ..
git diff --check
```

Expected: tests pass and no whitespace errors.

