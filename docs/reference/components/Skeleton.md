# Skeleton

## React Source

`frontend/app/components/ui/Skeleton.tsx`; named exports are re-exported by `ui/index.ts`.

## Public Props

| Export | Props and defaults |
| --- | --- |
| `SkeletonText` | `width: string \| number = "100%"`; numeric becomes px. `height = "h-4"`; `className = ""`. |
| `SkeletonAvatar` | `size = "h-8 w-8"`. |
| `SkeletonBadge` | No props. |
| `SkeletonRow` | `cols = 6`; optional `colWidths: string[]`; missing widths get deterministic inline percentages. |
| `SkeletonTableBody` | `rows = 8`; `cols = 6`; optional `colWidths`. |
| `SkeletonCard` | `lines = 3`. |
| `SkeletonCardGrid` | `count = 4`; `lines = 3`. |
| `SkeletonStatCard` | No props. |
| `SkeletonListItem` | No props. |
| `SkeletonList` | `rows = 5`. |

## Figma Properties

| Component | Proposed properties |
| --- | --- |
| Text | Width, height |
| Avatar | Size |
| Row/Table | Columns, rows, column-width composition |
| Card/Grid | Lines, count |
| List | Rows |

Status: pending Professional buildout. These map only to current named-export props.

## Required States

Light/dark shimmer; text/avatar/badge primitives; row/table, card/grid/stat-card, and list compositions at default and supported counts.

## Token Dependencies

Current shimmer, borders, and surfaces use hardcoded gray/white Tailwind classes; motion uses `animate-pulse`.

## Accessibility

All rendered placeholders are `aria-hidden`, directly or through hidden composition roots. Callers must expose loading status separately, such as `aria-busy` or accessible loading text. Reduced-motion handling is not local to this module.

## Tests

`frontend/__tests__/ui.Skeleton.test.tsx` covers hidden semantics, text height/numeric width, avatar/badge, card line count, grid count, row cells, table rows, stat card, and list rows. Gaps include `SkeletonListItem`, string widths, className, colWidths, defaults, dark styles, and reduced motion.

## Migration Notes

The audit baseline marks all six unique hardcoded neutral classes **Replace now** with shared loading, surface, and border tokens. No migration is claimed.

## Status

| React contract | Figma |
| --- | --- |
| Draft | Figma pending |
