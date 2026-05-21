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

### Requirement: Stakeholder demo mode remains useful with partial data
Stakeholder demo mode SHALL render a coherent empty or partial-data state when the corpus lacks enrichment, benchmark, concepts, or quality scores.

#### Scenario: Partial data does not crash the walkthrough
- **WHEN** `/dashboard/summary` returns missing optional intelligence modules
- **THEN** stakeholder demo mode renders fallback copy and keeps the export CTA disabled or contextual
