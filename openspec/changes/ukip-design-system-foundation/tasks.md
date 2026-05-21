## 1. Design system baseline

- [ ] 1.1 Inventory current `--ukip-*` tokens in `frontend/app/styles/tokens.css`.
- [ ] 1.2 Inventory current reusable UI components in `frontend/app/components/ui`.
- [ ] 1.3 Inventory UKIP-specific product components in `frontend/app/components/ukip`.
- [ ] 1.4 Identify duplicated visual patterns across dashboards, entity detail, reports, and import/review flows.
- [ ] 1.5 Document current light/dark theme behavior and confirm light mode remains default.

## 2. Token governance

- [ ] 2.1 Define semantic color roles for brand, intelligence, evidence, caution, risk, neutral, border, text, and focus.
- [ ] 2.2 Define spacing scale guidance for panels, compact controls, dense tables, dashboard grids, and mobile stacking.
- [ ] 2.3 Define radius and elevation usage rules.
- [ ] 2.4 Define typography usage guidance for headings, body copy, metrics, labels, identifiers, and dense data.
- [ ] 2.5 Define motion/transition guidance for hover, focus, expansion, loading, and disabled states.

## 3. Component foundation

- [ ] 3.1 Standardize Button and IconButton variants, sizes, states, and accessibility.
- [ ] 3.2 Standardize Input, Select, Textarea, Checkbox, Radio, Switch, and Toggle patterns.
- [ ] 3.3 Standardize Tabs, segmented controls, menus, and navigation affordances.
- [ ] 3.4 Standardize Panel, Surface, SectionHeader, EmptyState, ErrorBanner, Toast, and Skeleton patterns.
- [ ] 3.5 Standardize KPI, Metric, DeltaBadge, QualityBadge, and readiness/progress components.
- [ ] 3.6 Standardize DataTable and dense analytic table behavior.
- [ ] 3.7 Standardize visual banner, narrative banner, media callout, and report cover patterns.
- [ ] 3.8 Add usage examples or documentation comments for high-impact components.

## 4. Evidence and trust semantics

- [ ] 4.1 Define provenance badges for source, canonical, enrichment, authority, review, and audit states.
- [ ] 4.2 Define confidence indicators for high, medium, low, unknown, and review-required states.
- [ ] 4.3 Define null-state visual treatment for not-provided, pending-normalization, unresolved-enrichment, not-applicable, and unknown.
- [ ] 4.4 Define AI-assisted and AI-generated disclosure indicators.
- [ ] 4.5 Apply trust-state semantics to entity detail, reports, and review workflows.

## 5. UX surface alignment

- [ ] 5.1 Refactor dashboard widgets toward narrative metrics and next-action clarity.
- [ ] 5.2 Align entity detail with provenance layering UI.
- [ ] 5.3 Align import/mapping flows with source profiling and mapping suggestion states.
- [ ] 5.4 Align reports with executive readability and evidence traceability.
- [ ] 5.5 Align pilot mode surfaces with touch-friendly, clear, and calm controls.
- [ ] 5.6 Add multimedia banner patterns to onboarding, dashboard narrative surfaces, report covers, and empty states where useful.
- [ ] 5.7 Define when banners should be hidden, collapsed, or replaced by compact summaries for repeated-use workflows.

## 6. Accessibility and design QA

- [ ] 6.1 Add contrast expectations for semantic states in light and dark modes.
- [ ] 6.2 Add keyboard focus and hit-area expectations for controls.
- [ ] 6.3 Add responsive layout expectations for dashboard grids, tables, cards, and sidebars.
- [ ] 6.4 Add text overflow checks for buttons, badges, cards, panels, and table cells.
- [ ] 6.5 Add media accessibility checks for alt text, decorative media semantics, contrast overlays, reduced motion, and responsive cropping.
- [ ] 6.6 Add visual QA checklist for frontend pull requests.

## 7. Adoption governance

- [ ] 7.1 Require new frontend specs to declare design-system impact.
- [ ] 7.2 Define when new components belong in `components/ui` versus `components/ukip`.
- [ ] 7.3 Define migration order for legacy UI patterns.
- [ ] 7.4 Track design debt separately from product feature debt.
- [ ] 7.5 Document how product inspiration is translated without copying external brands.

## 8. Validation

- [ ] 8.1 Run `npx openspec validate ukip-design-system-foundation --strict`.
- [ ] 8.2 Run `npx openspec list`.
- [ ] 8.3 Validate consistency with `ukip-enterprise-architecture-governance`.
- [ ] 8.4 Validate consistency with `entity-provenance-layering` and `canonical-semantic-data-governance`.
