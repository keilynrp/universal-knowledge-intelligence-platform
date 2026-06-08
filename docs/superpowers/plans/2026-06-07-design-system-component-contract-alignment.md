# UKIP Design System Component Contract Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish tested React/Figma contracts and tokenized styling patterns for `Button`, `Badge`, `Input`, and `Select`, then document the remaining V1 components.

**Architecture:** Introduce semantic status tokens first, then use TDD to lock accessible component output and public props before replacing hardcoded visual classes. Keep layout utilities in Tailwind and visual roles in `--ukip-*`.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 4, CSS custom properties, Vitest, Testing Library. Spec: `docs/superpowers/specs/2026-06-07-design-system-component-contract-alignment-design.md`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `frontend/app/styles/tokens.css` | Additional semantic status tokens |
| `frontend/app/components/ui/Button.tsx` | Tokenized action primitive |
| `frontend/app/components/ui/Badge.tsx` | Tokenized status primitive |
| `frontend/app/components/ui/Input.tsx` | Accessible text-field contract |
| `frontend/app/components/ui/Select.tsx` | Accessible select contract |
| `frontend/__tests__/ui.Button.test.tsx` | Button API/accessibility tests |
| `frontend/__tests__/ui.Badge.test.tsx` | Badge semantic-token tests |
| `frontend/__tests__/ui.Input.test.tsx` | Input relationship tests |
| `frontend/__tests__/ui.Select.test.tsx` | Select relationship tests |
| `docs/reference/components/*.md` | React/Figma contracts for all V1 components |

---

### Task 1: Add status surface/text tokens

**Files:**
- Modify: `frontend/app/styles/tokens.css`
- Test: `frontend/__tests__/designTokens.audit.test.ts`

- [ ] **Step 1: Add failing token assertions**

Append assertions:

```ts
expect(result.declarations).toEqual(
  expect.arrayContaining([
    "--ukip-success-soft",
    "--ukip-warning-soft",
    "--ukip-danger-soft",
    "--ukip-info",
    "--ukip-info-soft",
  ]),
);
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
npx vitest run __tests__/designTokens.audit.test.ts
```

Expected: FAIL because the tokens are absent.

- [ ] **Step 3: Add Light/Dark tokens**

Add semantic values to both `:root` and `.dark` in `tokens.css`:

```css
--ukip-success-soft: oklch(94% 0.045 155);
--ukip-warning-soft: oklch(95% 0.055 78);
--ukip-danger-soft: oklch(94% 0.045 25);
--ukip-info: oklch(62% 0.16 245);
--ukip-info-soft: oklch(94% 0.04 245);
```

Use dark values with approximately 25-30% lightness and matching hue/chroma.

- [ ] **Step 4: Verify GREEN and commit**

```powershell
npx vitest run __tests__/designTokens.audit.test.ts
git add app/styles/tokens.css __tests__/designTokens.audit.test.ts
git commit -m "feat: add semantic status surface tokens"
```

---

### Task 2: Lock and tokenize Button

**Files:**
- Create: `frontend/__tests__/ui.Button.test.tsx`
- Modify: `frontend/app/components/ui/Button.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Button from "../app/components/ui/Button";

describe("Button", () => {
  it("defaults to type button and exposes disabled state", () => {
    render(<Button disabled>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toBeDisabled();
  });

  it("uses semantic UKIP tokens for primary and danger variants", () => {
    const { rerender } = render(<Button>Save</Button>);
    expect(screen.getByRole("button")).toHaveClass("bg-[var(--ukip-primary)]");
    rerender(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole("button")).toHaveClass("bg-[var(--ukip-danger)]");
  });

  it("renders optional icon slots", () => {
    render(<Button leftIcon={<span data-testid="left" />}>Save</Button>);
    expect(screen.getByTestId("left")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run and inspect RED/GREEN baseline**

Run:

```powershell
npx vitest run __tests__/ui.Button.test.tsx
```

If all assertions already pass, add a new assertion for `size="icon"` requiring
`aria-label`; this should fail until Step 3.

- [ ] **Step 3: Enforce accessible icon-only usage**

Add a development-time guard:

```tsx
if (process.env.NODE_ENV !== "production" && size === "icon" && !props["aria-label"]) {
  throw new Error("Button size=\"icon\" requires an aria-label");
}
```

Add a test expecting the error and another accepting `aria-label="Close"`.

- [ ] **Step 4: Verify and commit**

```powershell
npx vitest run __tests__/ui.Button.test.tsx
git add app/components/ui/Button.tsx __tests__/ui.Button.test.tsx
git commit -m "test: define accessible Button component contract"
```

---

### Task 3: Migrate Badge tests and styling to semantic tokens

**Files:**
- Modify: `frontend/__tests__/ui.Badge.test.tsx`
- Modify: `frontend/app/components/ui/Badge.tsx`

- [ ] **Step 1: Replace hardcoded-class assertions**

Change tests to expect:

```ts
expect(el?.className).toContain("bg-[var(--ukip-panel-strong)]");
expect(el?.className).toContain("bg-[var(--ukip-success-soft)]");
expect(el?.className).toContain("bg-[var(--ukip-danger-soft)]");
expect(el?.className).toContain("bg-[var(--ukip-warning-soft)]");
expect(el?.className).toContain("bg-[var(--ukip-info-soft)]");
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
npx vitest run __tests__/ui.Badge.test.tsx
```

Expected: the five updated class assertions fail.

- [ ] **Step 3: Replace `VARIANT_CLASSES`**

Use UKIP tokens:

```ts
default: {
  bg: "bg-[var(--ukip-panel-strong)]",
  text: "text-[var(--ukip-muted)]",
  dot: "bg-[var(--ukip-muted-soft)]",
},
success: {
  bg: "bg-[var(--ukip-success-soft)]",
  text: "text-[var(--ukip-emerald)]",
  dot: "bg-[var(--ukip-emerald)]",
},
```

Repeat for warning, error, info, and purple using the semantic UKIP tokens.

- [ ] **Step 4: Verify and commit**

```powershell
npx vitest run __tests__/ui.Badge.test.tsx
git add app/components/ui/Badge.tsx __tests__/ui.Badge.test.tsx
git commit -m "refactor: align Badge variants with UKIP tokens"
```

---

### Task 4: Add accessible Input relationships

**Files:**
- Create: `frontend/__tests__/ui.Input.test.tsx`
- Modify: `frontend/app/components/ui/Input.tsx`

- [ ] **Step 1: Write failing tests**

Test that:

```tsx
render(<Input id="email" label="Email" hint="Institutional address" />);
const input = screen.getByRole("textbox", { name: "Email" });
expect(input).toHaveAttribute("aria-describedby", "email-hint");
expect(screen.getByText("Institutional address")).toHaveAttribute("id", "email-hint");
```

Add an error case requiring `aria-invalid="true"` and
`aria-describedby="email-error"`.

- [ ] **Step 2: Verify RED**

Run:

```powershell
npx vitest run __tests__/ui.Input.test.tsx
```

Expected: accessible relationship assertions fail.

- [ ] **Step 3: Implement IDs and ARIA**

Derive:

```ts
const messageId = error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined;
```

Set `aria-invalid`, `aria-describedby`, and the message span `id`.

- [ ] **Step 4: Verify and commit**

```powershell
npx vitest run __tests__/ui.Input.test.tsx
git add app/components/ui/Input.tsx __tests__/ui.Input.test.tsx
git commit -m "feat: define accessible Input contract"
```

---

### Task 5: Add accessible Select relationships

Repeat Task 4 in:

- `frontend/__tests__/ui.Select.test.tsx`
- `frontend/app/components/ui/Select.tsx`

Use `getByRole("combobox", { name: "Country" })`. Verify RED, implement
`aria-invalid`/`aria-describedby`, verify GREEN, and commit:

```powershell
git commit -m "feat: define accessible Select contract"
```

---

### Task 6: Document V1 component contracts

**Files:**
- Create: `docs/reference/components/README.md`
- Create: `docs/reference/components/Button.md`
- Create: `docs/reference/components/Badge.md`
- Create: `docs/reference/components/Input.md`
- Create: `docs/reference/components/Select.md`
- Create: one contract file for each remaining V1 component

- [ ] **Step 1: Create the template**

Each file must include:

```markdown
# Component Name

## React Source
## Public Props
## Figma Properties
## Required States
## Token Dependencies
## Accessibility
## Tests
## Migration Notes
## Status
```

- [ ] **Step 2: Fill exact contracts**

Read each source component and record actual props. Do not invent a Figma
property that has no approved React/API meaning.

- [ ] **Step 3: Verify completeness**

Run:

```powershell
Get-ChildItem docs\reference\components\*.md | Select-Object Name
```

Expected: README plus ten V1 component files.

- [ ] **Step 4: Commit**

```powershell
git add docs/reference/components
git commit -m "docs: add UKIP V1 component contracts"
```

---

### Task 7: Final verification

Run:

```powershell
cd frontend
npx vitest run __tests__/designTokens.audit.test.ts __tests__/ui.Button.test.tsx __tests__/ui.Badge.test.tsx __tests__/ui.Input.test.tsx __tests__/ui.Select.test.tsx
npm run audit:design-tokens
npm run lint
```

Expected: all focused tests pass, audit exits 0, lint exits 0.
