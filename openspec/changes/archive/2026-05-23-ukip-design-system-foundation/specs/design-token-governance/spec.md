## ADDED Requirements

### Requirement: UKIP governs design tokens semantically
UKIP SHALL define and use design tokens according to semantic product roles rather than ad hoc visual preference.

#### Scenario: New color token is introduced
- **WHEN** a frontend change introduces a new color token
- **THEN** the token declares whether it supports brand, intelligence, evidence, caution, risk, neutral surface, text, border, or focus semantics
- **AND** the token includes light and dark mode behavior when applicable

#### Scenario: Existing component uses hardcoded colors
- **WHEN** a reusable component uses hardcoded visual colors for semantic state
- **THEN** the component should migrate toward UKIP design tokens or documented Tailwind semantic equivalents

#### Scenario: Color token follows semantic role rules
- **WHEN** a color token is defined
- **THEN** violet is reserved for brand accent and primary actions
- **AND** cyan supports intelligence and navigation emphasis
- **AND** emerald indicates evidence readiness, completion, or positive state
- **AND** amber indicates review, caution, or incomplete confidence
- **AND** red is reserved for errors, destructive actions, or high-risk states

#### Scenario: Decorative gradients are governed
- **WHEN** a gradient is used in the UI
- **THEN** it is limited to primary narrative surfaces and tied to brand or intelligence semantics
- **AND** does not appear on routine analytic controls or data surfaces

### Requirement: Light mode remains the default experience
UKIP SHALL keep light mode as the default visual experience regardless of system preference.

#### Scenario: User opens UKIP in a new browser
- **WHEN** there is no explicit stored theme preference
- **THEN** UKIP loads in light mode
- **AND** does not automatically adopt the operating system dark preference

#### Scenario: Dark mode is available by explicit choice
- **WHEN** the user explicitly selects dark mode
- **THEN** UKIP switches to dark mode with governed dark-mode token values
- **AND** the preference persists for that browser

### Requirement: Spacing scale supports analytic density
UKIP SHALL define spacing guidance that supports panels, compact controls, dense tables, dashboard grids, and responsive stacking.

#### Scenario: Interactive control has comfortable hit area
- **WHEN** a switch, button, tab, or icon control is rendered
- **THEN** it has a minimum touch target size suitable for repeated use

#### Scenario: Dashboard grid uses predictable spacing
- **WHEN** dashboard widgets are laid out in a grid
- **THEN** the spacing is consistent and does not nest cards inside decorative cards

#### Scenario: Dense table uses efficient spacing
- **WHEN** a data table displays many rows
- **THEN** row padding is compact enough for scanning without sacrificing readability

### Requirement: Typography usage is purpose-driven
UKIP SHALL define typography guidance for headings, body copy, metrics, labels, identifiers, and dense data.

#### Scenario: Metric emphasis uses tabular figures
- **WHEN** a KPI or metric value is displayed
- **THEN** it uses tabular or monospace number treatment for alignment

#### Scenario: Large display type is reserved for narrative surfaces
- **WHEN** large heading sizes are used
- **THEN** they appear only on hero or narrative surfaces, not on routine controls or dense data views

### Requirement: Radius, elevation, and motion follow hierarchy rules
UKIP SHALL define radius, elevation, and motion guidance that supports visual hierarchy without excessive decoration.

#### Scenario: Card uses modest radius
- **WHEN** a repeated card or control is rendered
- **THEN** it uses a modest border radius appropriate to its context

#### Scenario: Motion clarifies state transitions
- **WHEN** a UI element transitions between states (hover, focus, expansion, loading)
- **THEN** the transition uses a short duration and does not cause layout shift
