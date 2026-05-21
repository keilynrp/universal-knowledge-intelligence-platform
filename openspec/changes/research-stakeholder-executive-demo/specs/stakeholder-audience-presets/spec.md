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

### Requirement: Audience selection carries into reports
The selected stakeholder audience SHALL be passed from dashboard to report builder and reflected in exported brief framing.

#### Scenario: Audience is preserved during brief handoff
- **WHEN** a user selects an audience and opens the brief builder
- **THEN** the report builder initializes with that audience
- **AND** exported copy uses the audience-specific framing
