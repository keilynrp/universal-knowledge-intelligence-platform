## ADDED Requirements

### Requirement: Executive dashboard provides a shared decision readout
The executive dashboard SHALL present a decision readout with five parts: what we know, what is emerging, confidence, what is missing, and recommended action.

#### Scenario: Complete dashboard summary produces complete readout
- **WHEN** dashboard summary includes corpus KPIs, concepts, benchmark, quality, and recommendations
- **THEN** the decision readout includes known, emerging, confidence, missing, and recommended action sections

#### Scenario: Empty corpus produces cautious readout
- **WHEN** the dashboard summary has zero entities
- **THEN** the decision readout explains that the corpus is not yet sufficient for a stakeholder decision
- **AND** the recommended action points to import or demo seed

### Requirement: Report builder reuses the dashboard decision readout
The executive brief SHALL preserve the same decision readout that appears in the dashboard for the selected domain, benchmark profile, and audience.

#### Scenario: User opens brief builder from dashboard
- **WHEN** the user clicks "Prepare Executive Brief" from stakeholder demo mode
- **THEN** the report builder receives the selected domain, benchmark profile, audience, and decision readout context

#### Scenario: Export includes decision readout
- **WHEN** the user exports PDF or HTML
- **THEN** the exported artifact includes the decision readout sections
