## ADDED Requirements

### Requirement: Stakeholder audience presets adjust framing
The stakeholder demo and executive brief SHALL support audience presets that adjust framing, labels, and CTAs without changing underlying analytics calculations.

#### Scenario: Leadership audience emphasizes strategic action
- **WHEN** the leadership audience preset is selected
- **THEN** the readout emphasizes readiness, risk, and recommended institutional action

#### Scenario: Research office audience emphasizes operational gaps
- **WHEN** the research office audience preset is selected
- **THEN** the readout emphasizes coverage, quality, benchmark gaps, and repeatable review workflow

#### Scenario: Evaluator audience emphasizes defensibility
- **WHEN** the evaluator audience preset is selected
- **THEN** the readout emphasizes evidence, provenance, confidence, and limitations

#### Scenario: Investigator audience emphasizes evidence and impact
- **WHEN** the investigator/PI audience preset is selected
- **THEN** the readout emphasizes evidence quality, impact indicators, and next improvement steps

#### Scenario: Innovation/transfer audience emphasizes translational potential
- **WHEN** the innovation/transfer office audience preset is selected
- **THEN** the readout emphasizes translational potential, external attention signals, and collaboration opportunities

#### Scenario: Audience preset does not change calculations
- **WHEN** any audience preset is selected
- **THEN** the underlying analytics calculations, entity counts, and evidence references remain identical
- **AND** only labels, emphasis, CTAs, and report framing change

### Requirement: Audience selection carries into reports
The selected stakeholder audience SHALL be passed from dashboard to report builder and reflected in exported brief framing.

#### Scenario: Audience is preserved during brief handoff
- **WHEN** a user selects an audience and opens the brief builder
- **THEN** the report builder initializes with that audience
- **AND** exported copy uses the audience-specific framing

#### Scenario: Audience can be changed in report builder
- **WHEN** a user changes the audience in the report builder
- **THEN** the report framing updates to match the new audience
- **AND** the underlying data and evidence remain unchanged

#### Scenario: Default audience is leadership
- **WHEN** no audience has been explicitly selected
- **THEN** the dashboard and report builder default to the leadership audience preset

### Requirement: Audience selector is visible in stakeholder demo mode
UKIP SHALL provide an audience selector control when stakeholder demo mode is active.

#### Scenario: Audience selector is rendered
- **WHEN** stakeholder demo mode is active
- **THEN** an audience selector control is visible with all defined presets

#### Scenario: Audience selector shows preset descriptions
- **WHEN** the user interacts with the audience selector
- **THEN** each preset shows a brief description of its framing emphasis

### Requirement: Audience presets have EN/ES translations
UKIP SHALL provide localized translations for audience preset names, descriptions, and CTAs.

#### Scenario: English translations exist for audience presets
- **WHEN** the UI locale is English
- **THEN** all preset names, descriptions, and audience-specific CTAs are defined

#### Scenario: Spanish translations exist for audience presets
- **WHEN** the UI locale is Spanish
- **THEN** equivalent Spanish labels are defined for all audience preset copy
