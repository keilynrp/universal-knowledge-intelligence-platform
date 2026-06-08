# Badge

## React Source

`frontend/app/components/ui/Badge.tsx` (default export; re-exported by `ui/index.ts`).

## Public Props

| Prop | Type | Default | Contract |
| --- | --- | --- | --- |
| `children` | `React.ReactNode` | required | Badge label/content. |
| `variant` | `default \| success \| warning \| error \| info \| purple` | `default` | Semantic color role. |
| `dot` | `boolean` | falsy | Shows the status dot. |
| `dotPulse` | `boolean` | falsy | Adds a ping layer only when `dot` is true. |
| `size` | `sm \| md` | `sm` | Padding and text size. |

The component does not forward native span attributes or `className`.

## Figma Properties

| Property | Values |
| --- | --- |
| `Variant` | Default, Success, Warning, Error, Info, Purple |
| `Size` | Sm, Md |
| `Dot` | Boolean |
| `Dot pulse` | Boolean visual state; valid with Dot enabled |

Status: pending Professional buildout.

## Required States

Each variant at both sizes, with no dot, static dot, and pulsing dot.

## Token Dependencies

`--ukip-panel-strong`, `--ukip-muted`, `--ukip-muted-soft`, semantic `--ukip-{success,warning,danger,info}` foreground/soft pairs, and `--ukip-primary-soft`/`--ukip-violet`.

## Accessibility

The badge is a neutral `span`; semantic meaning must also be present in its text or surrounding accessible context. Pulse is decorative and currently has no reduced-motion override in this component.

## Tests

`frontend/__tests__/ui.Badge.test.tsx` covers content, every semantic variant and dot token, pulsing/static dot behavior, dot gating, and both sizes.

## Migration Notes

The current branch implements semantic status tokens and supersedes the audit baseline’s earlier “propose token” finding. No implementation change is claimed here.

## Status

| React contract | Figma |
| --- | --- |
| Contract implemented | Figma pending |
