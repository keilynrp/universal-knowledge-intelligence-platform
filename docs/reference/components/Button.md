# Button

## React Source

`frontend/app/components/ui/Button.tsx` (default export; re-exported by `ui/index.ts`).

## Public Props

Extends `ButtonHTMLAttributes<HTMLButtonElement>`.

| Prop | Type | Default | Contract |
| --- | --- | --- | --- |
| `variant` | `primary \| secondary \| ghost \| outline \| danger` | `primary` | Visual intent. |
| `size` | `sm \| md \| lg \| icon` | `md` | Control dimensions. |
| `leftIcon` | `ReactNode` | none | Rendered before children. |
| `rightIcon` | `ReactNode` | none | Rendered after children. |
| `type` | native button type | `button` | Prevents implicit form submission. |
| `className` | `string` | `""` | Appended after component classes. |
| `children` | native/React content | none | Button content. |

All other native button attributes are forwarded.

## Figma Properties

| Property | Values |
| --- | --- |
| `Variant` | Primary, Secondary, Ghost, Outline, Danger |
| `Size` | Sm, Md, Lg, Icon |
| `State` | Default, Hover, Focus, Disabled |
| `Left icon` / `Right icon` | Boolean instance visibility |

Status: pending Professional buildout.

## Required States

Default, hover, focus-visible, disabled, and icon-only. Loading and pressed states are not public contracts.

## Token Dependencies

`--ukip-primary`, `--ukip-primary-strong`, `--ukip-danger`, `--ukip-border`, `--ukip-panel-strong`, `--ukip-text`, `--ukip-text-strong`, `--ukip-muted`, `--ukip-radius-md`, `--ukip-glow-violet`, and the `ukip-focus` utility.

## Accessibility

Native button semantics and disabled behavior are preserved. In non-production builds, `size="icon"` throws unless a non-empty `aria-label` or `aria-labelledby` is supplied.

## Tests

`frontend/__tests__/ui.Button.test.tsx` covers default type, disabled forwarding, semantic primary/danger classes, icon order, all sizes, icon accessible names, and the production-only guard behavior.

## Migration Notes

The implemented contract uses semantic tokens. The audit baseline still identifies `hover:bg-violet-500/10` and `hover:border-violet-400/40` in secondary/outline states for replacement with approved interaction roles.

## Status

| Dimension | Status |
| --- | --- |
| Contract | Implemented |
| Token migration | Partial |
| Accessibility | Contract covered |
| Figma | Pending Professional buildout |
