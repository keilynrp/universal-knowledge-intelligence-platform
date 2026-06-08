# Select

## React Source

`frontend/app/components/ui/Select.tsx` (default export; re-exported by `ui/index.ts`).

## Public Props

Extends `SelectHTMLAttributes<HTMLSelectElement>`.

| Prop | Type | Default | Contract |
| --- | --- | --- | --- |
| `label` | `string` | none | Renders an associated label. |
| `hint` | `string` | none | Description shown when no error exists. |
| `error` | `string` | none | Error text; overrides hint and forces `aria-invalid=true`. |
| `children` | `ReactNode` | none | Native option/optgroup content. |
| `id` | native `string` | `name`, then `useId()` | Control/description identifier. |
| `className` | `string` | `""` | Appended to select classes. |
| `aria-describedby` | native string | none | Normalized, deduplicated, and merged with hint/error ID. |
| `aria-invalid` | native value | none | Preserved unless `error` is present. |

All remaining native select attributes are forwarded.

## Figma Properties

| Property | Values |
| --- | --- |
| `State` | Default, Focus, Open, Disabled, Error |
| `Label` | Boolean/text |
| `Supporting text` | None, Hint, Error |
| `Value state` | Placeholder, Selected |

Status: pending Professional buildout. “Open” documents the native visual state, not a controlled React prop.

## Required States

Labeled/unlabeled, hint, error, focus-visible, disabled, required, placeholder option, and selected value.

## Token Dependencies

`--ukip-radius-md`, `--ukip-border`, `--ukip-panel`, `--ukip-text`, `--ukip-muted`, `--ukip-danger`, and `ukip-focus`.

## Accessibility

Uses a native select. Label, ID generation, description merging, error precedence, and caller-provided ARIA values follow the Input contract.

## Tests

`frontend/__tests__/ui.Select.test.tsx` covers label/ID association, name and generated IDs, hint/error precedence, normalized descriptions, caller invalid state, native props, options, value, and class extension.

## Migration Notes

The current implementation is tokenized. Figma should model the closed control and native open-state intent without implying a custom listbox implementation.

## Status

| Dimension | Status |
| --- | --- |
| Contract | Implemented |
| Token migration | Complete |
| Accessibility | Contract covered |
| Figma | Pending Professional buildout |
