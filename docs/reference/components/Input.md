# Input

## React Source

`frontend/app/components/ui/Input.tsx` (default export; re-exported by `ui/index.ts`).

## Public Props

Extends `InputHTMLAttributes<HTMLInputElement>`.

| Prop | Type | Default | Contract |
| --- | --- | --- | --- |
| `label` | `string` | none | Renders an associated label. |
| `hint` | `string` | none | Description shown when no error exists. |
| `error` | `string` | none | Error text; overrides hint and forces `aria-invalid=true`. |
| `id` | native `string` | `name`, then `useId()` | Control/description identifier. |
| `className` | `string` | `""` | Appended to input classes. |
| `aria-describedby` | native string | none | Normalized, deduplicated, and merged with hint/error ID. |
| `aria-invalid` | native value | none | Preserved unless `error` is present. |

All remaining native input attributes are forwarded.

## Figma Properties

| Property | Values |
| --- | --- |
| `State` | Default, Focus, Disabled, Error |
| `Label` | Boolean/text |
| `Supporting text` | None, Hint, Error |
| `Value state` | Empty, Filled, Placeholder |

Status: pending Professional buildout.

## Required States

Unlabeled/accessibly named, labeled, hint, error, focus-visible, disabled, required, placeholder, and native input types.

## Token Dependencies

`--ukip-radius-md`, `--ukip-border`, `--ukip-panel`, `--ukip-text`, `--ukip-muted`, `--ukip-muted-soft`, `--ukip-danger`, and `ukip-focus`.

## Accessibility

Label association uses `htmlFor`. ID precedence is explicit `id`, then `name`, then `useId()`. Description IDs are deduplicated; error takes precedence over hint and sets invalid state.

## Tests

`frontend/__tests__/ui.Input.test.tsx` covers label/ID association, name and generated IDs, hint/error precedence, description merging, caller ARIA preservation, native props, and class extension.

## Migration Notes

The current implementation is tokenized and its accessibility contract is implemented. Figma must not represent browser-specific native input types as unsupported React variants.

## Status

| React contract | Figma |
| --- | --- |
| Contract implemented | Figma pending |
