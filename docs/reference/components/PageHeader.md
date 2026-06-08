# PageHeader

## React Source

`frontend/app/components/ui/PageHeader.tsx` (default export; re-exported by `ui/index.ts`).

## Public Props

| Prop | Type | Default | Contract |
| --- | --- | --- | --- |
| `title` | `string` | required | Rendered as the page `h1`. |
| `description` | `string` | none | Optional supporting copy. |
| `breadcrumbs` | `{ label: string; href?: string }[]` | none | Links when `href` exists; plain text otherwise. |
| `actions` | `React.ReactNode` | none | Right-aligned action slot on wider screens. |

## Figma Properties

| Property | Values |
| --- | --- |
| `Description` | Boolean/text |
| `Breadcrumbs` | Boolean; repeated item instances |
| `Actions` | Boolean/instance swap |
| `Layout` | Responsive stacked/inline state |

Status: pending Professional buildout.

## Required States

Title only; title with description; breadcrumbs with linked and current items; actions; narrow stacked and wide inline layouts.

## Token Dependencies

`--ukip-text-strong`, `--ukip-text`, `--ukip-muted`, `--ukip-muted-soft`, and `--ukip-cyan`.

## Accessibility

Provides one `h1` and a breadcrumb `nav` when items exist. The nav currently has no accessible label, separators are not hidden, and array-index keys are used; these are documented gaps.

## Tests

`frontend/__tests__/ui.PageHeader.test.tsx` covers the `h1`, optional description, breadcrumb rendering/link behavior, actions, and omitted navigation. It does not cover navigation labeling, separator exposure, or responsive layout.

## Migration Notes

No hardcoded color migration is identified by the audit baseline. Figma breadcrumb/action composition should reuse approved text, link, and Button patterns.

## Status

| React contract | Figma |
| --- | --- |
| Draft | Figma pending |
