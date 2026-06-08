# UKIP Design System Foundation Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved foundation-governance design into an auditable token inventory, drift report, review policy, and Figma Professional migration runbook.

**Architecture:** Keep `frontend/app/styles/tokens.css` as the technical authority and generate no automatic Figma writes in this plan. Documentation records the CSS/Figma mapping, while a small read-only Node audit checks token declarations and hardcoded UI values without modifying components.

**Tech Stack:** Markdown, CSS custom properties, Node.js, Vitest. Spec: `docs/superpowers/specs/2026-06-07-design-system-foundation-governance-design.md`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `docs/reference/UKIP_DESIGN_SYSTEM.md` | Canonical governance, token inventory, review policy |
| `docs/reference/UKIP_DESIGN_SYSTEM_TOKEN_AUDIT.md` | Baseline drift inventory and disposition |
| `docs/operating/FIGMA_PROFESSIONAL_DESIGN_SYSTEM_MIGRATION.md` | Exact Starter-to-Professional migration procedure |
| `frontend/scripts/audit-design-tokens.mjs` | Read-only CSS declaration and UI hardcode audit |
| `frontend/__tests__/designTokens.audit.test.ts` | Audit-script contract tests |
| `frontend/package.json` | `audit:design-tokens` command |

---

### Task 1: Add the token audit contract

**Files:**
- Create: `frontend/__tests__/designTokens.audit.test.ts`
- Create: `frontend/scripts/audit-design-tokens.mjs`

- [ ] **Step 1: Write the failing test**

Create `frontend/__tests__/designTokens.audit.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { auditTokenSource } from "../scripts/audit-design-tokens.mjs";

describe("design-token audit", () => {
  it("reports declarations, duplicates, and hardcoded UI color families", async () => {
    const result = await auditTokenSource();

    expect(result.declarations).toContain("--ukip-bg");
    expect(result.declarations).toContain("--ukip-space-4");
    expect(result.duplicates).toEqual([]);
    expect(result.hardcodedUsages).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ file: expect.stringContaining("Badge.tsx") }),
      ]),
    );
  });
});
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
npx vitest run __tests__/designTokens.audit.test.ts
```

Expected: FAIL because `scripts/audit-design-tokens.mjs` does not exist.

- [ ] **Step 3: Implement the read-only audit**

Create `frontend/scripts/audit-design-tokens.mjs`:

```js
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TOKEN_FILE = path.join(ROOT, "app", "styles", "tokens.css");
const UI_DIR = path.join(ROOT, "app", "components", "ui");
const TOKEN_RE = /^\s*(--ukip-[a-z0-9-]+):/gm;
const HARDCODED_RE =
  /\b(?:bg|text|border|ring|shadow)-(?:gray|slate|red|amber|yellow|green|emerald|blue|cyan|violet|purple)-[0-9]+(?:\/[0-9]+)?/g;

export async function auditTokenSource() {
  const css = await fs.readFile(TOKEN_FILE, "utf8");
  const declarations = [...css.matchAll(TOKEN_RE)].map((match) => match[1]);
  const counts = new Map();
  for (const token of declarations) counts.set(token, (counts.get(token) ?? 0) + 1);

  const files = (await fs.readdir(UI_DIR)).filter((name) => name.endsWith(".tsx"));
  const hardcodedUsages = [];
  for (const file of files) {
    const source = await fs.readFile(path.join(UI_DIR, file), "utf8");
    const matches = [...source.matchAll(HARDCODED_RE)].map((match) => match[0]);
    if (matches.length) hardcodedUsages.push({ file, matches: [...new Set(matches)] });
  }

  return {
    declarations: [...new Set(declarations)].sort(),
    duplicates: [...counts].filter(([, count]) => count > 2).map(([name]) => name),
    hardcodedUsages,
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const result = await auditTokenSource();
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (result.duplicates.length) process.exitCode = 1;
}
```

The duplicate threshold is `> 2` because theme-dependent color tokens normally
appear once in `:root` and once in `.dark`.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
npx vitest run __tests__/designTokens.audit.test.ts
```

Expected: 1 test file passed.

- [ ] **Step 5: Commit**

```powershell
git add frontend/scripts/audit-design-tokens.mjs frontend/__tests__/designTokens.audit.test.ts
git commit -m "test: add UKIP design token drift audit"
```

---

### Task 2: Expose the audit command and capture the baseline

**Files:**
- Modify: `frontend/package.json`
- Create: `docs/reference/UKIP_DESIGN_SYSTEM_TOKEN_AUDIT.md`

- [ ] **Step 1: Add the package script**

Add under `scripts` in `frontend/package.json`:

```json
"audit:design-tokens": "node scripts/audit-design-tokens.mjs"
```

- [ ] **Step 2: Run the audit**

Run:

```powershell
npm run audit:design-tokens
```

Expected: JSON with token declarations, no duplicate errors, and current
hardcoded usages.

- [ ] **Step 3: Write the baseline report**

Create `docs/reference/UKIP_DESIGN_SYSTEM_TOKEN_AUDIT.md` with:

```markdown
# UKIP Design System Token Audit

**Baseline date:** 2026-06-07
**Command:** `cd frontend && npm run audit:design-tokens`

## Disposition

| Category | Rule |
| --- | --- |
| Replace now | Existing semantic UKIP token expresses the same role |
| Propose token | Repeated semantic role has no UKIP token |
| Keep | Layout utility or intentionally local data-visualization color |

## Current Findings

Paste the command's reviewed `hardcodedUsages` list here and assign each file one
of the dispositions above. Do not refactor components in this plan.
```

Replace the instruction paragraph with the actual reviewed findings before
committing.

- [ ] **Step 4: Commit**

```powershell
git add frontend/package.json docs/reference/UKIP_DESIGN_SYSTEM_TOKEN_AUDIT.md
git commit -m "docs: record UKIP design token drift baseline"
```

---

### Task 3: Harden governance documentation

**Files:**
- Modify: `docs/reference/UKIP_DESIGN_SYSTEM.md`

- [ ] **Step 1: Add governance sections**

Add sections covering:

```markdown
## Token Classes

Primitive, semantic, component, and utility tokens follow the definitions in
the Foundation Governance spec. V1 prefers semantic tokens.

## Token Change Review

| Change | Required evidence |
| --- | --- |
| Add | semantic need, existing-token search, Light/Dark values |
| Value | visual comparison and contrast check |
| Rename | usage search and migration note |
| Remove | zero-usage evidence and deprecation period |

## Drift Audit

Run `cd frontend && npm run audit:design-tokens`. Review findings rather than
blindly replacing visualization or product-specific colors.
```

- [ ] **Step 2: Verify documented tokens exist**

Run:

```powershell
npm run audit:design-tokens
```

Expected: exit code 0.

- [ ] **Step 3: Commit**

```powershell
git add docs/reference/UKIP_DESIGN_SYSTEM.md
git commit -m "docs: define UKIP foundation governance"
```

---

### Task 4: Write the Professional migration runbook

**Files:**
- Create: `docs/operating/FIGMA_PROFESSIONAL_DESIGN_SYSTEM_MIGRATION.md`

- [ ] **Step 1: Write the runbook**

Include exact phases:

```markdown
# Figma Professional Design System Migration

## Preconditions
- Professional plan active for Key's team.
- Current CSS token audit passes.
- Figma variable export/inspection recorded before mutation.

## Migration
1. Create `UKIP/Color` with `Light` and `Dark` modes.
2. Recreate each semantic name from the paired Starter collections.
3. Preserve WEB code syntax exactly.
4. Compare all 20 Light and 20 Dark values.
5. Build a disposable binding probe for fill, stroke, and text.
6. Only after validation, mark Starter collections deprecated.

## Rollback
Keep `UKIP/Color/Light` and `UKIP/Color/Dark` until every probe and component
passes. If any binding fails, restore use of the Starter collections and record
the affected variable IDs.
```

Add the full 20-token checklist from `tokens.css`.

- [ ] **Step 2: Validate links and formatting**

Run:

```powershell
git diff --check -- docs/operating/FIGMA_PROFESSIONAL_DESIGN_SYSTEM_MIGRATION.md
```

Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```powershell
git add docs/operating/FIGMA_PROFESSIONAL_DESIGN_SYSTEM_MIGRATION.md
git commit -m "docs: add Figma Professional migration runbook"
```

---

### Task 5: Final verification

- [ ] Run:

```powershell
cd frontend
npm run audit:design-tokens
npx vitest run __tests__/designTokens.audit.test.ts
```

Expected: both commands exit 0.

- [ ] Run:

```powershell
git diff --check
```

Expected: no whitespace errors.
