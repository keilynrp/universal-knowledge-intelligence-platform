# UKIP Design System Token Audit Baseline

Date: 2026-06-07

Command:

```bash
cd frontend
npm run audit:design-tokens
```

## Provenance

- Audited token source: `frontend/app/styles/tokens.css`
- Audited component path: `frontend/app/components/ui/*.tsx`
- Current branch: `codex/design-system-governance`
- Branch base: `41cf380`
- Audit logic commits: `e2f13ba`, `00536f2`, `1aaf543`
- Baseline report/package commit: `b5703e2`
- Token addition commit: `b228fbc`
- `frontend/app/styles/tokens.css` SHA-256 at audit time: `5be593c58739f7d9759972699954d0cd633841534048de0dcd572ea707a95f67`
- The 44-token count includes the approved Design System token additions committed in `b228fbc`. The fingerprint identifies that exact token-file state.

## Baseline

- Declared `--ukip-*` tokens: 44
- Duplicate token declarations: 0
- UI files with hardcoded Tailwind color classes: 15
- Sum of per-file unique hardcoded Tailwind color class entries: 246
- Globally distinct hardcoded Tailwind color classes: 167

The audit reports unique class names per file, not occurrence counts. Because the same class can appear in multiple files, the 246 entry count is the sum of each file's unique class list rather than a globally distinct count.

## Disposition Rules

- **Replace now**: A design-system primitive uses a hardcoded color for shared structure, interaction, typography, border, surface, or focus state and an existing token expresses the intent.
- **Propose token**: A reusable semantic state is valid, but the current token set does not express all required foreground, background, border, and dark-mode roles. Add an approved semantic token family before replacing it.
- **Keep**: The color is intentionally local to product meaning, a KPI/data-visualization series, or a bounded illustrative palette. It should not become a global design-system primitive token without broader reuse.

## Reviewed Findings

| File | Classes | Disposition | Review |
| --- | ---: | --- | --- |
| `Badge.tsx` | 30 | Propose token | Shared status primitive. Propose neutral, success, warning, danger, info, and accent badge foreground/background/dot roles. |
| `Button.tsx` | 2 | Replace now | Shared interaction primitive; violet hover background and outline border should use existing primary/focus roles. |
| `ConceptTooltip.tsx` | 3 | Replace now | Shared interaction primitive; hover text/background and focus ring should use primary/focus tokens. |
| `DataTable.tsx` | 24 | Replace now | Shared table chrome, selection, pagination, text, borders, surfaces, and controls belong to existing design-system roles. |
| `DeltaBadge.tsx` | 11 | Propose token | Reusable positive/negative/neutral semantic indicator. Propose semantic foreground/background roles; do not treat direction colors as chart-series tokens. |
| `EmptyState.tsx` | 37 | Replace now + Keep | **Keep (24):** icon palette groups `bg-{blue,violet,emerald,amber,rose}-50`, `bg-{blue,violet,emerald,amber,rose}-900/20`, `text-{blue,violet,emerald,amber,rose}-500`, `text-{blue,violet,emerald,amber,rose}-400`, plus `bg-slate-100`, `bg-slate-800`, `text-slate-400`, `text-slate-500`. **Replace now (13):** `text-gray-900`, `text-gray-100`, `text-gray-500`, `text-gray-400`, `bg-blue-600`, `bg-blue-700`, `border-gray-300`, `text-gray-700`, `bg-gray-50`, `border-gray-600`, `bg-gray-800`, `text-gray-300`, `bg-gray-700`. |
| `ErrorBanner.tsx` | 25 | Propose token | Shared danger feedback primitive needs danger foreground, muted foreground, background, border, and interaction roles beyond the single `--ukip-danger` value. |
| `KpiSummaryCard.tsx` | 21 | Keep + Replace now | **Keep (16):** KPI icon groups `bg-{violet,amber,emerald,sky}-100`, `text-{violet,amber,emerald,sky}-700`, `bg-{violet,amber,emerald,sky}-400/15`, `text-{violet,amber,emerald,sky}-200`. **Replace now (5):** `border-slate-200`, `border-violet-200`, `border-violet-400/30`, `text-slate-600`, `text-slate-950`. |
| `Metric.tsx` | 12 | Keep | Violet/cyan/emerald/amber gradients are an explicit metric visualization palette; structural chrome already uses tokens. |
| `QualityBadge.tsx` | 5 | Keep + Replace now | **Keep (3):** score thresholds `bg-emerald-500`, `bg-amber-400`, `bg-red-500`. **Replace now (2):** neutral track `bg-slate-200`, `bg-slate-700/70`. |
| `Skeleton.tsx` | 6 | Replace now | Loading placeholders are design-system primitives; neutral shimmer, card surface, and border colors should use shared tokens. |
| `StatCard.tsx` | 10 | Keep | Icon tones are a bounded product/data-display palette; structural panel and typography already use tokens. |
| `Surface.tsx` | 1 | Replace now | Shared raised-surface border should use a design-system border/focus role rather than a literal violet class. |
| `TabNav.tsx` | 15 | Replace now | Shared navigation primitive; active, hover, badge, text, and border states should use existing primary, muted, surface, and border roles. |
| `Toast.tsx` | 44 | Propose token | Shared feedback primitive. Propose success, danger, warning, and info foreground/background/border/progress roles before migration. |

## Baseline Decision

This report records drift only; no component refactor is part of this baseline. Foundation primitives are the first replacement candidates. Semantic feedback components require approved token families, while product and data-visualization palettes remain local unless repeated use establishes a cross-product semantic contract.
