## ADDED Requirements

### Requirement: Stakeholder demo mode opens the executive journey
The executive dashboard SHALL support a stakeholder demo mode that guides research stakeholders from corpus readiness to exportable decision brief.

#### Scenario: Dashboard opens in stakeholder demo mode
- **WHEN** a user visits `/analytics/dashboard?mode=stakeholder-demo`
- **THEN** the page displays a guided walkthrough rail for the research stakeholder journey
- **AND** the dashboard still displays the normal executive analytics content

#### Scenario: Demo seed success links to stakeholder demo mode
- **WHEN** demo data is seeded successfully
- **THEN** the primary follow-up CTA points to `/analytics/dashboard?mode=stakeholder-demo`

#### Scenario: Import success links to stakeholder demo mode
- **WHEN** a user completes a data import successfully
- **THEN** a secondary CTA offers to open the dashboard in stakeholder demo mode

### Requirement: Stakeholder walkthrough exposes four decision steps
The stakeholder walkthrough SHALL include these steps: corpus readiness, executive signal, evidence behind recommendation, and export stakeholder brief.

#### Scenario: Walkthrough renders all decision steps
- **WHEN** stakeholder demo mode is active
- **THEN** the user can see the four steps in order
- **AND** each step links to the relevant dashboard section or action

#### Scenario: Walkthrough can be dismissed
- **WHEN** the user dismisses the walkthrough
- **THEN** the dashboard remains usable
- **AND** the dismissal is persisted for that browser

#### Scenario: Walkthrough can be reset
- **WHEN** the user clicks "Reset walkthrough"
- **THEN** the walkthrough returns to step 1
- **AND** the reset is persisted for that browser

#### Scenario: Walkthrough step highlights relevant dashboard section
- **WHEN** the user activates a walkthrough step
- **THEN** the corresponding dashboard section or widget receives visual emphasis
- **AND** the walkthrough rail scrolls to maintain context

### Requirement: Stakeholder demo mode remains useful with partial data
Stakeholder demo mode SHALL render a coherent empty or partial-data state when the corpus lacks enrichment, benchmark, concepts, or quality scores.

#### Scenario: Partial data does not crash the walkthrough
- **WHEN** `/dashboard/summary` returns missing optional intelligence modules
- **THEN** stakeholder demo mode renders fallback copy and keeps the export CTA disabled or contextual

#### Scenario: Zero entities shows import guidance
- **WHEN** the dashboard has zero entities in stakeholder demo mode
- **THEN** the walkthrough shows import or demo seed guidance as the recommended next step

#### Scenario: Enrichment not run shows enrichment guidance
- **WHEN** entities exist but enrichment has not run
- **THEN** the walkthrough step for executive signal shows enrichment recommendation
- **AND** the evidence step shows a caveat about limited evidence

### Requirement: Stakeholder demo mode is testable
UKIP SHALL include frontend tests for stakeholder demo rendering and walkthrough behavior.

#### Scenario: Test verifies walkthrough rendering with complete data
- **WHEN** a test provides a complete dashboard summary in stakeholder demo mode
- **THEN** all four walkthrough steps render with populated content

#### Scenario: Test verifies walkthrough rendering with empty data
- **WHEN** a test provides an empty dashboard summary in stakeholder demo mode
- **THEN** the walkthrough renders fallback guidance without errors

#### Scenario: Test verifies dismiss and reset behavior
- **WHEN** a test simulates dismiss and reset interactions
- **THEN** the walkthrough state changes correctly
