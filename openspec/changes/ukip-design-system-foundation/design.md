## Context

UKIP already has the beginnings of a design system:

- `frontend/app/styles/tokens.css` defines `--ukip-*` design tokens.
- `frontend/app/styles/globals.css` defines reusable shell, panel, chip, focus, and selection utilities.
- `frontend/app/components/ui/` contains reusable UI primitives.
- `frontend/app/components/ukip/` contains UKIP-specific product components.
- Recent work made light mode the default and improved the pilot mode switch interaction.

The foundation is real, but it is not yet governed. This spec turns that foundation into a deliberate design system layer under `ukip-enterprise-architecture-governance`.

## Goals / Non-Goals

**Goals:**
- Define UKIP's design system principles and visual direction.
- Govern token usage across light/dark themes.
- Define component expectations for reusable UI primitives and UKIP-specific patterns.
- Create visual semantics for evidence, provenance, authority, enrichment, confidence, review, and AI-generated content.
- Improve UX consistency across dashboards, reports, entity details, import/review flows, and executive surfaces.
- Support incremental adoption rather than a disruptive redesign.

**Non-Goals:**
- Copy Nubank's design system or brand.
- Redesign every screen immediately.
- Replace Tailwind CSS.
- Build a full external design documentation site in the first iteration.
- Freeze product iteration while the design system evolves.
- Make the interface decorative at the expense of analytic density.

## Design Principles

### 1. Fresh, not frivolous

UKIP should feel modern and distinctive, but its UI must support scientific and institutional trust. Violet can carry brand energy; neutral surfaces and disciplined hierarchy carry credibility.

### 2. Evidence before expression

Visual treatments must help users understand source, confidence, provenance, authority, enrichment, and AI-generated status. Color should communicate meaning before decoration.

### 3. Calm density

UKIP is an analytic product. Screens can be information-rich, but they should be organized for scanning, comparison, and repeated use.

### 4. Light by default

Light mode is the default product experience, independent of system preference. Dark mode can remain available by explicit user choice.

### 5. Components are contracts

Core components should encode spacing, state, accessibility, and interaction behavior so feature screens do not reinvent small decisions repeatedly.

### 6. AI is visible and governed

GenAI-assisted content must be visually distinguishable where stakeholder trust depends on it. The UI should show evidence grounding, review status, or confidence when relevant.

## Token Domains

### Color

Token families should cover:

- brand: violet primary and strong/soft variants,
- intelligence: cyan accents,
- evidence/completion: emerald,
- caution/review: amber,
- risk/error: red,
- neutral surface hierarchy,
- text hierarchy,
- borders,
- focus rings.

Color usage rules:

- Violet is the brand accent, not the only visual language.
- Cyan should support intelligence/navigation, not compete with primary actions.
- Emerald should indicate evidence readiness, completion, or positive state.
- Amber should indicate review, caution, or incomplete confidence.
- Red should be reserved for errors, destructive actions, or high-risk states.
- Decorative gradients should be limited and tied to primary narrative surfaces.

### Typography

Typography should support:

- executive scanning,
- dense analytic tables,
- compact controls,
- narrative report sections,
- metric emphasis,
- code/identifier legibility.

Rules:

- Use stable, readable sizes rather than viewport-scaled typography.
- Reserve large display sizes for true hero/narrative surfaces.
- Use tabular/mono treatment for numeric metrics and identifiers when useful.
- Avoid negative letter spacing except where already intentionally defined for large headings.

### Spacing and Layout

Spacing should support:

- clear control touch targets,
- scan-friendly cards and panels,
- predictable dashboard grids,
- efficient tables,
- responsive stacking.

Rules:

- Interactive controls should have comfortable hit areas.
- UI cards should not nest inside other decorative cards.
- Page sections should avoid unnecessary framed containers.
- Fixed-format components should use stable dimensions to prevent layout shift.

### Radius and Elevation

Radius and elevation should help hierarchy without making every surface feel like a floating card.

Rules:

- Repeated cards and controls may use modest radii.
- Tool surfaces, modals, and product-specific panels can use larger radii when justified.
- Shadows should be subtle in analytic surfaces.
- Glow effects should be rare and purposeful.

### Motion and Interaction

Motion should clarify state, not entertain.

Rules:

- Use short transitions for hover, focus, expansion, and active state.
- Avoid layout-shifting hover states.
- Loading, empty, error, and disabled states must be explicit.
- Keyboard focus states must be visible and consistent.

## Component Foundation

Initial component families:

- Button / IconButton
- Input / Select / Textarea
- Switch / Toggle / Checkbox / Radio
- Tabs / segmented controls
- Badge / provenance badge / confidence badge
- KPI card / metric panel / delta indicator
- Panel / surface / section header
- Data table
- Empty state
- Error banner / toast
- Skeleton/loading state
- Evidence card / source citation item
- Visual banner / narrative banner / media callout
- Rich media container / image treatment / video or animation slot
- AI disclosure indicator

Each component should define:

- purpose,
- variants,
- sizes,
- states,
- accessibility requirements,
- token usage,
- responsive behavior,
- examples of correct and incorrect use.

## Evidence and Provenance Visual Semantics

UKIP-specific semantic states:

- `source`: original ingestion value,
- `canonical`: UKIP normalized identity,
- `enrichment`: external provider observation,
- `authority`: resolved authority link,
- `review`: needs human confirmation,
- `confidence-high`,
- `confidence-medium`,
- `confidence-low`,
- `ai-assisted`,
- `ai-generated`,
- `not-provided`,
- `pending-normalization`,
- `unresolved-enrichment`,
- `not-applicable`.

These states should have consistent visual treatment across:

- entity detail,
- mapping suggestions,
- reconciliation review,
- dashboards,
- reports,
- AI-generated narratives,
- evidence panels.

## UX Surface Guidance

### Dashboards

Dashboards should tell a decision story:

- current state,
- readiness,
- evidence gaps,
- next action,
- confidence limits.

KPI widgets should be narratively useful, not merely descriptive.

### Entity Detail

Entity detail should show:

- original ingestion data,
- canonical identity,
- enrichment observations,
- authority/audit data,
- null reasons,
- confidence/review status.

### Import and Mapping

Import/mapping UI should make source profiling and mapping suggestions reviewable.

### Reports

Reports should preserve executive readability while exposing evidence and confidence where needed.

### Visual Banners and Multimedia Narrative

UKIP should support richer visual storytelling through governed banner patterns. These banners are not decorative hero blocks by default; they should help orient, persuade, teach, or frame a decision journey.

Useful banner types:

- onboarding banner: introduces a workflow or pilot path,
- stakeholder banner: frames a dashboard/report for a specific audience,
- evidence journey banner: explains source to canonical to enrichment to report flow,
- data readiness banner: highlights whether a dataset can support a narrative,
- empty-state banner: turns a blank state into a guided action,
- report cover banner: gives generated reports a stronger executive artifact feel,
- feature announcement banner: introduces a new capability without interrupting work,
- AI-assisted banner: clarifies when AI is helping and how evidence is grounded.

Banner content may include:

- title and supporting copy,
- primary and secondary action,
- short metrics,
- provenance/evidence tags,
- illustration, generated bitmap, product screenshot, simple motion, or contextual image,
- audience/stakeholder label,
- confidence or review status where relevant.

Banner rules:

- The banner must have a clear job: orient, explain, frame, guide, or convert.
- The visual asset must relate to the actual product, data, workflow, evidence, or stakeholder context.
- Banners should not push core task controls below the fold without a strong reason.
- Banners should not rely on gradient-only decoration.
- Text must remain readable over images and across responsive sizes.
- Media must include accessible alternatives or be decorative with correct semantics.
- Motion must be optional, subtle, and non-blocking.
- AI-generated imagery must be appropriate for scientific intelligence and should not imply false evidence.

### AI-Assisted Surfaces

AI outputs should show whether they are suggestions, draft narratives, evidence-grounded summaries, or reviewed outputs.

## Rollout Strategy

1. Document current tokens and component primitives.
2. Define missing token semantics.
3. Create component inventory and gap list.
4. Standardize high-impact controls first: buttons, switchers, tabs, badges, KPI cards, panels, tables.
5. Define visual banner and multimedia narrative components for onboarding, dashboards, reports, and empty states.
6. Apply provenance/confidence state semantics to entity detail and reports.
7. Refactor dashboards toward narrative metric widgets.
8. Add visual QA checks for responsive layout, contrast, and text overflow.

## Risks / Trade-offs

- **Risk: Over-styling the product.** Mitigation: Use color as semantic signal first.
- **Risk: Design system slows feature work.** Mitigation: Adopt incrementally and prioritize high-impact primitives.
- **Risk: Existing screens diverge during migration.** Mitigation: Component inventory and staged refactors.
- **Risk: Dark mode reappears as accidental default.** Mitigation: Keep default theme behavior governed and tested.
- **Risk: AI states are hidden.** Mitigation: Define explicit AI disclosure components.
- **Risk: Banners become marketing decoration.** Mitigation: Require each banner to declare its narrative job and evidence/stakeholder context.

## Relationship to Enterprise Architecture

Primary domain:

- UX/UI Experience Architecture

Secondary domains:

- Business & Stakeholder Architecture
- Data & Semantic Architecture
- GenAI Cross-Cutting Capability
- Security, Privacy & Compliance

Related specs:

- `ukip-enterprise-architecture-governance`
- `entity-provenance-layering`
- `canonical-semantic-data-governance`
- `research-stakeholder-executive-demo`
