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

#### Scenario: Input and select components are used
- **WHEN** a form requires text input, select, textarea, checkbox, or radio controls
- **THEN** the controls follow governed patterns with consistent sizing, label placement, error display, and focus behavior

#### Scenario: Tabs or segmented control is used
- **WHEN** a screen uses tabs or a segmented control for navigation or filtering
- **THEN** the control follows governed patterns with consistent active/inactive styling, keyboard navigation, and responsive behavior

#### Scenario: Panel and section header are used
- **WHEN** a screen groups content into sections or panels
- **THEN** the layout uses governed panel, surface, and section-header components with consistent padding, border, and hierarchy

#### Scenario: KPI card and metric panel are used
- **WHEN** a dashboard displays key performance indicators
- **THEN** the widgets use governed KPI card, metric panel, delta badge, or quality badge components
- **AND** metric values use tabular figure treatment

#### Scenario: Data table is used
- **WHEN** a screen displays tabular data
- **THEN** the table follows governed patterns for column alignment, row density, sorting, horizontal scroll, and responsive behavior

#### Scenario: Empty state, error banner, and skeleton are used
- **WHEN** a screen has no data, encounters an error, or is loading
- **THEN** the UI uses governed empty-state, error-banner, toast, or skeleton components
- **AND** the empty state provides guidance toward a next action when appropriate

### Requirement: Reusable components preserve responsive stability
Reusable components SHALL avoid layout shift and text overflow across supported viewport sizes.

#### Scenario: KPI card receives long translated text
- **WHEN** a KPI card label or helper text is longer in a translated language
- **THEN** the card layout remains readable without overlapping adjacent content

#### Scenario: Dense table is shown on a narrow viewport
- **WHEN** a data table exceeds available width
- **THEN** the table provides predictable horizontal scrolling or responsive disclosure behavior

#### Scenario: Badge with long text does not break layout
- **WHEN** a badge or provenance label contains long translated text
- **THEN** it truncates or wraps gracefully without pushing adjacent elements

### Requirement: Component usage examples are documented
UKIP SHALL provide usage examples or documentation comments for high-impact components.

#### Scenario: High-impact component has usage guidance
- **WHEN** a developer uses a button, KPI card, data table, or provenance badge
- **THEN** documentation comments or examples show correct and incorrect usage patterns
