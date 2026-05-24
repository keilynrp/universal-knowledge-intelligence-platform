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

#### Scenario: Partial enrichment produces qualified readout
- **WHEN** the dashboard summary has entities but incomplete enrichment
- **THEN** the decision readout presents available data with explicit coverage caveats
- **AND** the confidence section reflects enrichment gaps

#### Scenario: Missing benchmark produces limited confidence
- **WHEN** the dashboard summary has no benchmark rules configured
- **THEN** the confidence section indicates that benchmark-based assessment is unavailable
- **AND** the recommended action suggests configuring benchmark rules

#### Scenario: Missing concept signals produce qualified emerging section
- **WHEN** the dashboard summary has no concept or topic data
- **THEN** the emerging section indicates that topic analysis is unavailable
- **AND** the recommended action suggests running enrichment or adding concept sources

### Requirement: DecisionReadout interface is shared across dashboard and reports
UKIP SHALL define a shared `DecisionReadout` TypeScript interface used by both the dashboard and the report builder.

#### Scenario: Dashboard uses DecisionReadout interface
- **WHEN** the dashboard renders a decision readout
- **THEN** it uses the shared `DecisionReadout` interface

#### Scenario: Report builder uses DecisionReadout interface
- **WHEN** the report builder generates decision readout sections
- **THEN** it uses the same `DecisionReadout` interface as the dashboard

#### Scenario: DecisionReadout builder derives from dashboard summary
- **WHEN** the builder receives a `/dashboard/summary` payload
- **THEN** it produces a `DecisionReadout` with known, emerging, confidence, missing, and recommended_action sections

### Requirement: Report builder reuses the dashboard decision readout
The executive brief SHALL preserve the same decision readout that appears in the dashboard for the selected domain, benchmark profile, and audience.

#### Scenario: User opens brief builder from dashboard
- **WHEN** the user clicks "Prepare Executive Brief" from stakeholder demo mode
- **THEN** the report builder receives the selected domain, benchmark profile, audience, and decision readout context

#### Scenario: Export includes decision readout
- **WHEN** the user exports PDF or HTML
- **THEN** the exported artifact includes the decision readout sections

#### Scenario: Export includes evidence appendix
- **WHEN** the user exports a stakeholder brief
- **THEN** the exported artifact includes an evidence appendix referencing benchmark rules, entity filters, concept sources, and quality thresholds that support the readout claims

### Requirement: DecisionReadout builder handles edge cases
UKIP SHALL include unit and regression tests for the DecisionReadout builder with complete, partial, and empty payloads.

#### Scenario: Test verifies complete readout
- **WHEN** a test provides a full dashboard summary with KPIs, concepts, benchmarks, and quality
- **THEN** the builder produces a complete DecisionReadout with all five sections populated

#### Scenario: Test verifies partial readout
- **WHEN** a test provides a dashboard summary with entities but no concepts or benchmarks
- **THEN** the builder produces a qualified readout with caveat copy in the emerging and confidence sections

#### Scenario: Test verifies empty readout
- **WHEN** a test provides a dashboard summary with zero entities
- **THEN** the builder produces a cautious readout with import/seed recommendation
