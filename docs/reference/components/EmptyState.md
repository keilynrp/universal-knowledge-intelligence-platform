# EmptyState

## React Source

`frontend/app/components/ui/EmptyState.tsx` (default export; re-exported by `ui/index.ts`).

## Public Props

| Prop | Type | Default | Contract |
| --- | --- | --- | --- |
| `icon` | preset key or `ReactNode` | `entities` | Presets: entities, search, chart, sparkles, bell, key, users, bolt, document. Unknown strings fall back to entities at runtime. |
| `title` | `string` | required | Rendered as `h3`. |
| `description` | `string` | none | Optional supporting copy. |
| `cta` | CTA item or CTA item array | none | Item is link `{label, href, variant?}` or button `{label, onClick, variant?}`. |
| `color` | `blue \| violet \| emerald \| amber \| slate \| rose` | `slate` | Icon bubble palette. |
| `size` | `page \| card \| compact` | `card` | Vertical padding: 24, 14, or 8. |
| `className` | `string` | `""` | Appended to root classes. |

CTA `variant` is `primary | secondary`; omitted means primary.

## Figma Properties

| Property | Values |
| --- | --- |
| `Size` | Page, Card, Compact |
| `Icon color` | Blue, Violet, Emerald, Amber, Slate, Rose |
| `Description` | Boolean/text |
| `CTA count` | None, One, Two-or-more composition |
| `CTA variant` | Primary, Secondary |

Status: pending Professional buildout.

## Required States

All sizes/colors, preset/custom icon, description absent/present, no CTA, link CTA, button CTA, and multiple CTAs.

## Token Dependencies

Current text and CTA chrome use hardcoded gray/blue families. The six icon schemes are a local illustrative palette.

## Accessibility

Title is an `h3`; callers must place it at the correct heading level. Link/button semantics follow CTA type, but buttons omit explicit `type="button"`. Preset SVGs are not marked decorative and CTA arrays use index keys.

## Tests

`frontend/__tests__/ui.EmptyState.test.tsx` covers title/description, link and button CTAs, multiple CTAs, page/compact padding, and one preset icon. Gaps include default/card size, colors, custom/fallback icons, CTA styles, and accessibility details.

## Migration Notes

Audit disposition: keep the 24 icon-palette classes; replace 13 shared text/CTA/surface classes with tokens. No component migration is claimed.

## Status

| React contract | Figma |
| --- | --- |
| Draft | Figma pending |
