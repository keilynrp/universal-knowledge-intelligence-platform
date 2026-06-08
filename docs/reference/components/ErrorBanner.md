# ErrorBanner

## React Source

`frontend/app/components/ui/ErrorBanner.tsx` (default export; re-exported by `ui/index.ts`).

## Public Props

| Prop | Type | Default | Contract |
| --- | --- | --- | --- |
| `message` | `string` | required | Primary error message. |
| `detail` | `string` | none | Shown by card and row; ignored by inline. |
| `onRetry` | `() => void` | none | Shows variant-specific retry button. |
| `variant` | `inline \| card \| row` | `card` | Layout and retry label. |
| `className` | `string` | `""` | Appended to the selected root. |

Inline retry text is “Retry”; card and row use “Try again”.

## Figma Properties

| Property | Values |
| --- | --- |
| `Variant` | Inline, Card, Row |
| `Detail` | Boolean/text; unavailable in Inline |
| `Retry` | Boolean |
| `Message` | Text |

Status: pending Professional buildout.

## Required States

Each variant with message only, detail where supported, retry absent/present, hover, focus, and long card detail.

## Token Dependencies

Current component uses hardcoded red danger families and gray text plus white/transparent surfaces across light/dark states.

## Accessibility

Every variant has `role="alert"` and decorative SVGs use `aria-hidden`. Retry buttons lack explicit `type="button"`, and repeated live alerts may be announced immediately.

## Tests

`frontend/__tests__/ui.ErrorBanner.test.tsx` covers message, alert role, card detail/retry, omitted retry, and inline/row callbacks. Gaps include inline detail suppression, classes, button type, long detail, and focus behavior.

## Migration Notes

The audit baseline says **Propose token**: danger foreground, muted foreground, background, border, and interaction roles must be approved before replacing all 25 hardcoded classes.

## Status

| Dimension | Status |
| --- | --- |
| Contract | Draft |
| Token migration | Pending |
| Accessibility | Reviewed with follow-ups |
| Figma | Pending Professional buildout |
