# UKIP Design System — Documentation & Maintenance Workflow Design

**Date:** 2026-06-07
**Status:** Draft for iterative review
**Related:** Foundation Governance, Component Contract Alignment, Figma Library Buildout
**Depends on:** `docs/reference/UKIP_DESIGN_SYSTEM.md`

---

## 1. Problem & Goal

A design system fails quietly when its rules live only in memory. UKIP needs a
maintenance workflow that tells contributors how to propose tokens, update
components, review Figma changes, verify implementation, and record migration
notes.

**Goal:** define documentation and maintenance rituals that keep the Figma
library, React implementation, and reference docs coherent as the system evolves.

### Non-goals

- No heavyweight governance board.
- No automated publishing workflow in this spec.
- No requirement that every product screen be redesigned immediately.

---

## 2. Documentation Surfaces

| Surface | Purpose |
| --- | --- |
| `docs/reference/UKIP_DESIGN_SYSTEM.md` | Canonical overview and operating contract |
| `docs/superpowers/specs/*design-system*.md` | Design decisions and implementation-ready specs |
| Figma `Getting Started` page | Designer-facing usage and contribution guide |
| Figma component pages | Visual API, variants, examples, usage notes |
| Component tests | Executable implementation contract |

The reference doc stays concise. Specs carry design rationale. Figma pages carry
visual usage.

---

## 3. Change Workflow

### A. New Token

1. Explain semantic need.
2. Search existing tokens.
3. Add CSS token or document Figma-only draft status.
4. Add Figma variable with matching code syntax.
5. Verify Light/Dark behavior.
6. Update documentation and migration notes.

### B. Component Change

1. Update component contract first.
2. Add or update tests.
3. Refactor implementation.
4. Update Figma component.
5. Validate accessibility and states.
6. Record migration notes if API or visuals changed.

### C. Figma-Only Exploration

Exploratory work is allowed, but it is not production-ready until the contract
and implementation mapping exist. Label exploratory frames clearly and keep them
out of published component pages.

---

## 4. Versioning

Use simple semantic design-system versions:

- **Patch:** documentation clarification, non-breaking token value correction.
- **Minor:** additive token or component variant.
- **Major:** token rename/removal, component prop API change, broad visual shift.

V1 remains pre-release until:

- foundations are documented visually;
- first four components have contracts and Figma pages;
- maintenance workflow is tested on at least one real change.

---

## 5. Ownership

| Area | Owner role |
| --- | --- |
| Token naming and semantics | Design + frontend |
| CSS implementation | Frontend |
| Figma library structure | Design-system maintainer |
| Accessibility rules | Frontend + product/design |
| Release notes | Change author |

Ownership is role-based, not person-based, so it survives team changes.

---

## 6. Review Checklists

### Foundation Review

- Is the token semantic?
- Does a matching CSS variable exist?
- Does WEB code syntax match?
- Are Light and Dark values paired?
- Is contrast acceptable for intended use?

### Component Review

- Does the Figma API match React props?
- Are states represented without variant explosion?
- Are tokens bound instead of hardcoded values?
- Is focus visible?
- Is disabled behavior clear?
- Are tests present for implementation behavior?

### Documentation Review

- Is the change discoverable from the reference doc or Figma Getting Started?
- Are migration notes included for breaking changes?
- Are examples realistic but not product-specific?

---

## 7. Implementation Slices

### Slice 1 — Reference Doc Expansion

- Add change workflow.
- Add review checklists.
- Add versioning policy.

### Slice 2 — Component Template

- Create a repeatable component documentation template.
- Use it first for `Button`.

### Slice 3 — Changelog

- Add a design-system changelog section or file.
- Record Figma Starter foundation creation and future Professional migration.

### Slice 4 — Contribution Loop

- Run one real component through the workflow.
- Adjust checklist based on friction found.

---

## 8. Validation

- Docs link to the right source files and Figma file.
- No document claims a component is complete before tests and Figma validation.
- Review checklists do not conflict with Foundation Governance.
- Changelog entries distinguish draft, approved, and implemented changes.

---

## 9. Risks

| Risk | Mitigation |
| --- | --- |
| Docs become stale | Keep reference concise and update it in the same change as code/Figma |
| Process slows small fixes | Use lightweight checklists, not ceremony |
| Figma and code releases differ | Label status clearly: draft, approved, implemented |
| Contributors bypass the system | Make the component template easy to copy |

---

## 10. Acceptance Criteria

- A contributor can propose a token or component change without asking where to
  document it.
- Reviewers have a shared checklist.
- The docs clearly distinguish design draft from production-ready contract.
- V1 can evolve iteratively without losing traceability.
