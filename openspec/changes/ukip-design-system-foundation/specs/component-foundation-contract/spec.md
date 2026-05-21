## ADDED Requirements

### Requirement: Core UI components define reusable variants and states
UKIP SHALL define reusable component contracts for common UI primitives.

#### Scenario: Button component is used
- **WHEN** a screen needs a primary, secondary, destructive, or icon-only action
- **THEN** it should use the governed button or icon-button pattern
- **AND** preserve hover, active, disabled, loading, and focus-visible states

#### Scenario: Switch or toggle component is used
- **WHEN** a user toggles a product mode or binary setting
- **THEN** the control provides a comfortable hit area, visible state, keyboard accessibility, and clear label context

### Requirement: Reusable components preserve responsive stability
Reusable components SHALL avoid layout shift and text overflow across supported viewport sizes.

#### Scenario: KPI card receives long translated text
- **WHEN** a KPI card label or helper text is longer in a translated language
- **THEN** the card layout remains readable without overlapping adjacent content

#### Scenario: Dense table is shown on a narrow viewport
- **WHEN** a data table exceeds available width
- **THEN** the table provides predictable horizontal scrolling or responsive disclosure behavior
