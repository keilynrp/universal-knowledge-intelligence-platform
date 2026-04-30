# UKIP Design System

UKIP uses a dark-first, cognitive SaaS interface for semantic intelligence work: dense enough for expert workflows, calm enough for long analysis sessions, and modular enough to evolve without redesigning every screen.

## Principles

- **Dark-first foundation.** Dark mode is the polished primary surface. Light mode must remain readable and functional.
- **Semantic tokens before one-off classes.** New UI should use `--ukip-*` tokens or shared components rather than hard-coded colors.
- **Progressive adoption.** Preserve routes, API behavior, auth, i18n, and role logic. Migrate screen-by-screen after the shell and shared primitives stabilize.
- **Cognitive density.** Prefer compact hierarchy, strong labels, visible state, and flat metadata groups over nested cards that fight variable-length content.
- **One visual language.** Catalog records, portal records, shell surfaces, and dashboard panels should feel like parts of the same intelligence platform.

## Token Interface

The stable styling interface lives in `frontend/app/styles/tokens.css`.

Core color tokens:

```css
--ukip-bg;
--ukip-surface;
--ukip-panel;
--ukip-border;
--ukip-text;
--ukip-muted;
--ukip-primary;
--ukip-violet;
--ukip-cyan;
--ukip-emerald;
--ukip-warning;
--ukip-danger;
```

Shape and depth tokens:

```css
--ukip-radius-sm;
--ukip-radius-md;
--ukip-radius-lg;
--ukip-radius-xl;
--ukip-shadow-panel;
--ukip-glow-violet;
```

Tailwind v4 maps the tokens through `@theme inline` in the app global stylesheet. CSS tokens remain the source of truth; `frontend/tailwind.config.ts` exists only for editor and tooling compatibility.

## Component Rules

- Use shared primitives from `frontend/app/components/ui` for buttons, inputs, panels, metrics, icon buttons, and section headers.
- Use layout primitives from `frontend/app/components/layout` for page shells, toolbars, content grids, and sidebar grouping.
- Use UKIP-specific primitives from `frontend/app/components/ukip` for enrichment, semantic panels, cognitive KPIs, knowledge cards, and portal/catalog record cards.
- Keep component APIs small and composable. Do not encode API fetching or route behavior in design components.
- Use rounded panels with soft borders and subtle glow sparingly. Data readability beats decoration.

## Adaptive Narrative Blocks

UKIP uses adaptive narrative blocks to reduce fragmented onboarding messages.

These blocks combine:

- product explanation
- current user progress
- recommended next step
- reason for the recommendation
- primary CTA

They should be used when the interface needs to guide the user through complex knowledge workflows.

### Rules

- One primary narrative block per screen.
- Avoid competing recommendation cards.
- The narrative must adapt to system state.
- Recommendations must explain why the action matters.
- CTAs must be specific and operational.

## Migration Policy

1. Start with shell, global background, focus states, and shared record cards.
2. Replace repeated screen-level panel patterns with `Panel`, `Surface`, and `PageShell`.
3. Move catalog and portal record views toward `PortalRecordCard` / `RecordResultCard` instead of creating parallel card systems.
4. Migrate Settings, Reports, Import, Widgets, and Analytics in later passes using the same primitives.

## Example

```tsx
import { Button, Panel, SectionHeader } from "@/app/components/ui";
import { EnrichmentMeter, SignalBadge } from "@/app/components/ukip";

<Panel variant="cognitive">
  <SectionHeader eyebrow="Semantic signal" title="Collection readiness" />
  <SignalBadge tone="violet">Enriched</SignalBadge>
  <EnrichmentMeter value={70} />
  <Button>Open intelligence view</Button>
</Panel>
```
