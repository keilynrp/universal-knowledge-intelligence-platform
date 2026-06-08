# StatCard

## React Source

`frontend/app/components/ui/StatCard.tsx` (default export; re-exported by `ui/index.ts`). Depends on `DeltaBadge`.

## Public Props

| Prop | Type | Default | Contract |
| --- | --- | --- | --- |
| `icon` | `React.ReactNode` | required | Icon slot. |
| `iconColor` | `blue \| emerald \| amber \| violet \| red \| gray` | `blue` | Bounded icon palette. |
| `label` | `ReactNode` | required | Metric label. |
| `value` | `string \| number` | required | Primary metric. |
| `trend` | `{ value: string; direction: up \| down \| neutral; positive?: boolean }` | none | Renders `DeltaBadge`. |
| `subtitle` | `string` | none | Optional supporting text. |

Trend mapping is currently: neutral stays neutral; otherwise `positive === false` maps down; all other values map up.

## Figma Properties

| Property | Values |
| --- | --- |
| `Icon color` | Blue, Emerald, Amber, Violet, Red, Gray |
| `Trend` | None, Up, Down, Neutral |
| `Subtitle` | Boolean/text |
| `Icon` | Instance swap |

Status: pending Professional buildout.

## Required States

Each icon color, string/numeric value, optional subtitle, and trend absent/up/down/neutral.

## Token Dependencies

Structural `ukip-panel-soft`, `--ukip-text-strong`, `--ukip-muted`, and `--ukip-muted-soft`. Icon colors use local cyan/emerald/amber/violet/red Tailwind classes plus tokenized gray.

## Accessibility

The component has no landmark or metric-specific semantics. Callers must make decorative icons hidden or provide appropriate accessible content. Trend meaning must not rely on color alone; `DeltaBadge` text/value is required.

## Tests

`frontend/__tests__/ui.StatCard.test.tsx` covers label, string/numeric values, subtitle presence, trend presence, and icon rendering. Gaps: icon colors and trend-direction mapping are not asserted.

## Migration Notes

The audit baseline marks the bounded icon palette **Keep**; structural panel and typography already use tokens. Do not globalize these palette colors without broader reuse.

## Status

| React contract | Figma |
| --- | --- |
| Draft | Figma pending |
