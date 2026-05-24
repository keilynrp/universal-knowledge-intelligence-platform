## ADDED Requirements

### Requirement: New frontend specs declare design-system impact
UKIP frontend specs SHALL declare how they use, extend, or intentionally defer the design system.

#### Scenario: New dashboard feature is proposed
- **WHEN** a spec introduces a dashboard or metric component
- **THEN** it identifies existing design-system components to reuse
- **AND** declares any new component variants or tokens needed

#### Scenario: New trust-state UI is proposed
- **WHEN** a spec introduces provenance, confidence, authority, enrichment, review, or AI state UI
- **THEN** it aligns with `evidence-provenance-ui-semantics`

#### Scenario: Spec defers design-system alignment
- **WHEN** a spec intentionally defers design-system alignment for speed
- **THEN** it declares the deferral and records the design debt for later migration

### Requirement: Design system adoption is incremental and tracked
UKIP SHALL migrate existing UI toward the design system through prioritized, non-disruptive increments.

#### Scenario: Legacy UI pattern is found
- **WHEN** an existing screen has duplicated or inconsistent component styling
- **THEN** the design debt is recorded or addressed in a focused refactor
- **AND** unrelated product behavior is not changed unless necessary

#### Scenario: Migration order follows impact priority
- **WHEN** the design system team prioritizes migration work
- **THEN** high-impact primitives (buttons, tabs, badges, KPI cards, panels, tables) are migrated before low-impact patterns

#### Scenario: Design debt is tracked separately from feature debt
- **WHEN** design inconsistencies are identified
- **THEN** they are recorded as design debt items distinct from product feature backlog

### Requirement: Component ownership boundaries are defined
UKIP SHALL define when new components belong in `components/ui` versus `components/ukip`.

#### Scenario: Generic reusable component is created
- **WHEN** a new component has no UKIP-specific domain semantics (e.g., a button, input, or table)
- **THEN** it belongs in `components/ui`

#### Scenario: UKIP-specific product component is created
- **WHEN** a new component encodes UKIP domain semantics (e.g., provenance badge, authority readiness card, decision readout)
- **THEN** it belongs in `components/ukip`

### Requirement: Product inspiration is governed
UKIP SHALL document how external design inspiration is translated into UKIP-specific patterns without copying brand identity.

#### Scenario: External design inspiration is adopted
- **WHEN** UKIP adopts visual direction inspired by an external product
- **THEN** the adoption translates the inspiration into scientific intelligence, evidence trust, and stakeholder decision semantics
- **AND** avoids copying the external product brand expression, color palette, or marketing patterns directly
