# UKIP Design System Token Audit Baseline

Date: 2026-06-07

Command:

```bash
cd frontend
npm run audit:design-tokens
```

## Baseline

- Declared `--ukip-*` tokens: 44
- Duplicate token declarations: 0
- UI files with hardcoded Tailwind color classes: 15
- Distinct classes reported across files: 246

The audit reports unique class names per file, not occurrence counts.

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
| `EmptyState.tsx` | 37 | Replace now + Keep | Replace shared text, CTA, border, and surface colors. Keep the bounded icon illustration palette (`blue`, `violet`, `emerald`, `amber`, `slate`, `rose`) local. |
| `ErrorBanner.tsx` | 25 | Propose token | Shared danger feedback primitive needs danger foreground, muted foreground, background, border, and interaction roles beyond the single `--ukip-danger` value. |
| `KpiSummaryCard.tsx` | 21 | Keep + Replace now | Keep KPI icon tones as local data-display colors. Replace card surface, border, text, and generic hover chrome with existing tokens when the component is refactored. |
| `Metric.tsx` | 12 | Keep | Violet/cyan/emerald/amber gradients are an explicit metric visualization palette; structural chrome already uses tokens. |
| `QualityBadge.tsx` | 5 | Keep + Replace now | Keep score thresholds (emerald/amber/red) local to quality meaning; replace the neutral track with a shared muted/surface role. |
| `Skeleton.tsx` | 6 | Replace now | Loading placeholders are design-system primitives; neutral shimmer, card surface, and border colors should use shared tokens. |
| `StatCard.tsx` | 10 | Keep | Icon tones are a bounded product/data-display palette; structural panel and typography already use tokens. |
| `Surface.tsx` | 1 | Replace now | Shared raised-surface border should use a design-system border/focus role rather than a literal violet class. |
| `TabNav.tsx` | 15 | Replace now | Shared navigation primitive; active, hover, badge, text, and border states should use existing primary, muted, surface, and border roles. |
| `Toast.tsx` | 44 | Propose token | Shared feedback primitive. Propose success, danger, warning, and info foreground/background/border/progress roles before migration. |

## Baseline Decision

This report records drift only; no component refactor is part of this baseline. Foundation primitives are the first replacement candidates. Semantic feedback components require approved token families, while product and data-visualization palettes remain local unless repeated use establishes a cross-product semantic contract.
