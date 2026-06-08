# TabNav

## React Source

`frontend/app/components/ui/TabNav.tsx` (default export; re-exported by `ui/index.ts`).

## Public Props

| Prop | Type | Default | Contract |
| --- | --- | --- | --- |
| `tabs` | `{ id: string; label: string; badge?: string \| number }[]` | required | Ordered tab definitions. |
| `activeTab` | `string` | required | ID used to set active styling and `aria-selected`. |
| `onTabChange` | `(tabId: string) => void` | required | Called on click. |

## Figma Properties

| Property | Values |
| --- | --- |
| `State` | Active, Inactive, Hover, Focus |
| `Badge` | Boolean/text |
| `Label` | Text |
| `Overflow` | Single-line horizontal scrolling composition |

Status: pending Professional buildout.

## Required States

Active, inactive, hover, focus-visible, badge/no badge, and horizontal overflow.

## Token Dependencies

Current implementation uses hardcoded gray and blue Tailwind families for borders, text, hover, active, badge, and dark states.

## Accessibility

Uses `tablist`, `tab`, `aria-selected`, an accessible tablist label, and `type="button"`. Gaps: no keyboard arrow/Home/End behavior, roving `tabIndex`, `aria-controls`, or associated tabpanel IDs.

## Tests

`frontend/__tests__/ui.TabNav.test.tsx` covers labels, active/inactive classes, click callback, and optional badge. It does not test ARIA selection or keyboard behavior.

## Migration Notes

The audit baseline marks all shared navigation colors **Replace now** with primary, muted, surface, and border roles. This documentation does not claim that migration has occurred.

## Status

| React contract | Figma |
| --- | --- |
| Draft | Figma pending |
