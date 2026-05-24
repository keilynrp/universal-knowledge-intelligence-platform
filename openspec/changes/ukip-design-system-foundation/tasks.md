## 1. Design system baseline

- [x] 1.1 Inventory current `--ukip-*` tokens in `frontend/app/styles/tokens.css`.
- [x] 1.2 Inventory current reusable UI components in `frontend/app/components/ui`.
- [x] 1.3 Inventory UKIP-specific product components in `frontend/app/components/ukip`.
- [x] 1.4 Identify duplicated visual patterns across dashboards, entity detail, reports, and import/review flows.
- [x] 1.5 Document current light/dark theme behavior and confirm light mode remains default.

## 2. Token governance

- [x] 2.1 Define semantic color roles for brand, intelligence, evidence, caution, risk, neutral, border, text, and focus.
- [x] 2.2 Define spacing scale guidance for panels, compact controls, dense tables, dashboard grids, and mobile stacking.
- [x] 2.3 Define radius and elevation usage rules.
- [x] 2.4 Define typography usage guidance for headings, body copy, metrics, labels, identifiers, and dense data.
- [x] 2.5 Define motion/transition guidance for hover, focus, expansion, loading, and disabled states.

## 3. Component foundation

- [x] 3.1 Standardize Button and IconButton variants, sizes, states, and accessibility.
- [x] 3.2 Standardize Input, Select, Textarea, Checkbox, Radio, Switch, and Toggle patterns.
- [x] 3.3 Standardize Tabs, segmented controls, menus, and navigation affordances.
- [x] 3.4 Standardize Panel, Surface, SectionHeader, EmptyState, ErrorBanner, Toast, and Skeleton patterns.
- [x] 3.5 Standardize KPI, Metric, DeltaBadge, QualityBadge, and readiness/progress components.
- [x] 3.6 Standardize DataTable and dense analytic table behavior.
- [x] 3.7 Standardize visual banner, narrative banner, media callout, and report cover patterns.
- [x] 3.8 Add usage examples or documentation comments for high-impact components.

## 4. Evidence and trust semantics

- [x] 4.1 Define provenance badges for source, canonical, enrichment, authority, review, and audit states.
- [x] 4.2 Define confidence indicators for high, medium, low, unknown, and review-required states.
- [x] 4.3 Define null-state visual treatment for not-provided, pending-normalization, unresolved-enrichment, not-applicable, and unknown.
- [x] 4.4 Define AI-assisted and AI-generated disclosure indicators.
- [x] 4.5 Apply trust-state semantics to entity detail, reports, and review workflows.

## 5. UX surface alignment

- [x] 5.1 Refactor dashboard widgets toward narrative metrics and next-action clarity.
- [x] 5.2 Align entity detail with provenance layering UI.
- [x] 5.3 Align import/mapping flows with source profiling and mapping suggestion states.
- [x] 5.4 Align reports with executive readability and evidence traceability.
- [x] 5.5 Align pilot mode surfaces with touch-friendly, clear, and calm controls.
- [x] 5.6 Add multimedia banner patterns to onboarding, dashboard narrative surfaces, report covers, and empty states where useful.
- [x] 5.7 Define when banners should be hidden, collapsed, or replaced by compact summaries for repeated-use workflows.

## 6. Accessibility and design QA

- [x] 6.1 Add contrast expectations for semantic states in light and dark modes.
- [x] 6.2 Add keyboard focus and hit-area expectations for controls.
- [x] 6.3 Add responsive layout expectations for dashboard grids, tables, cards, and sidebars.
- [x] 6.4 Add text overflow checks for buttons, badges, cards, panels, and table cells.
- [x] 6.5 Add media accessibility checks for alt text, decorative media semantics, contrast overlays, reduced motion, and responsive cropping.
- [x] 6.6 Add visual QA checklist for frontend pull requests.

## 7. Adoption governance

- [x] 7.1 Require new frontend specs to declare design-system impact.
- [x] 7.2 Define when new components belong in `components/ui` versus `components/ukip`.
- [x] 7.3 Define migration order for legacy UI patterns.
- [x] 7.4 Track design debt separately from product feature debt.
- [x] 7.5 Document how product inspiration is translated without copying external brands.

## 8. Validation

- [x] 8.1 Run `npx openspec validate ukip-design-system-foundation --strict`.
- [x] 8.2 Run `npx openspec list`.
- [x] 8.3 Validate consistency with `ukip-enterprise-architecture-governance`.
- [x] 8.4 Validate consistency with `entity-provenance-layering` and `canonical-semantic-data-governance`.
