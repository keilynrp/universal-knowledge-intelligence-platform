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

### Requirement: Design system adoption is incremental and tracked
UKIP SHALL migrate existing UI toward the design system through prioritized, non-disruptive increments.

#### Scenario: Legacy UI pattern is found
- **WHEN** an existing screen has duplicated or inconsistent component styling
- **THEN** the design debt is recorded or addressed in a focused refactor
- **AND** unrelated product behavior is not changed unless necessary
