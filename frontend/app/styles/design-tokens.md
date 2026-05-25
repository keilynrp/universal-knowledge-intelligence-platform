# Design Token Governance — Task 5.4

## Semantic Color Roles

| Token | Role | Usage |
|-------|------|-------|
| `--ukip-violet` / `--ukip-primary` | Brand / Identity | Logo, nav active, brand accent |
| `--ukip-cyan` | Intelligence / AI | AI badges, skill indicators, enrichment |
| `--ukip-emerald` | Evidence / Success | Confirmed, evidence-backed, resolved |
| `--ukip-warning` (amber) | Caution / Review | Review required, pending, stale |
| `--ukip-danger` (red) | Risk / Error | Failed, rejected, violations |

## Rules

1. **Light mode is default.** The `.dark` class is opt-in, never auto-adopted from OS preference.
2. **Violet is brand-only.** Do not use violet for data status or semantic meaning.
3. **Cyan marks AI/intelligence.** Any AI-produced content uses cyan as accent.
4. **Emerald marks evidence.** Confirmed authority, high-confidence evidence, resolved status.
5. **Amber marks review states.** Pending review, stale candidates, low-confidence suggestions.
6. **Red marks failures.** Rejected, failed, governance violations.

## Spacing Guidance

| Context | Spacing |
|---------|---------|
| Dashboard grid gap | `1.5rem` (24px) |
| Panel internal padding | `1.25rem` (20px) |
| Table row height (dense) | `2.5rem` (40px) |
| Touch target minimum | `44px × 44px` |
| Section gap | `2rem` (32px) |

## Typography

- **Tabular figures** (`font-variant-numeric: tabular-nums`) for all metrics/KPIs.
- **Large type** (> 2rem) only on narrative/hero surfaces, never in data tables.
- **Body text** stays `0.875rem`–`1rem` for readability in dense layouts.

## Radius Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--ukip-radius-sm` | 0.5rem | Chips, badges, small controls |
| `--ukip-radius-md` | 0.75rem | Buttons, inputs |
| `--ukip-radius-lg` | 1rem | Cards, panels |
| `--ukip-radius-xl` | 1.25rem | Modal corners |
| `--ukip-radius-2xl` | 1.5rem | Hero/feature cards |
