## ADDED Requirements

### Requirement: Epistemic analytics page
The system SHALL provide a page at `/analytics/epistemic` showing paradigm distribution and temporal evolution for the active domain.

#### Scenario: Page loads with classified data
- **WHEN** user navigates to /analytics/epistemic
- **AND** the active domain has entities with epistemic profiles
- **THEN** the page displays a paradigm distribution chart, temporal evolution chart, and summary statistics

#### Scenario: Page loads with no classified data
- **WHEN** user navigates to /analytics/epistemic
- **AND** no entities have epistemic profiles
- **THEN** the page displays an empty state with explanation and a "Classify Now" button (visible only to admins)

#### Scenario: Page loads for domain without epistemology config
- **WHEN** user navigates to /analytics/epistemic
- **AND** the active domain has no epistemology configuration
- **THEN** the page displays a message indicating epistemic analysis is not configured for this domain

### Requirement: Paradigm distribution chart
The page SHALL display a donut/pie chart showing the proportion of entities per paradigm, plus a count of unclassified entities.

#### Scenario: Distribution with three paradigms
- **WHEN** the domain has empiricist (60%), constructivist (25%), critical (15%) distribution
- **THEN** the chart shows three colored segments with labels and percentages

#### Scenario: Hover on chart segment
- **WHEN** user hovers over a paradigm segment
- **THEN** a tooltip shows the paradigm label and exact count/percentage

### Requirement: Temporal evolution chart
The page SHALL display an area chart showing paradigm distribution over time (by publication year).

#### Scenario: Temporal trend with multiple years
- **WHEN** the domain has entities spanning 2015-2025
- **THEN** the area chart shows stacked paradigm proportions per year

### Requirement: Batch classify button for admins
Admin users SHALL see a "Classify Entities" button that triggers batch classification.

#### Scenario: Admin clicks classify button
- **WHEN** admin clicks "Classify Entities"
- **THEN** the system calls POST /analytics/epistemic/{domain_id}/classify
- **AND** shows a toast with the count of classified entities on success

#### Scenario: Viewer does not see classify button
- **WHEN** a viewer user opens the epistemic analytics page
- **THEN** the "Classify Entities" button is not rendered

### Requirement: Sidebar navigation entry
The sidebar SHALL include an "Epistemic Analysis" item under the Analytics section linking to /analytics/epistemic.

#### Scenario: Sidebar shows epistemic analysis link
- **WHEN** user views the sidebar
- **THEN** an "Epistemic Analysis" item appears under Analytics with an appropriate icon

### Requirement: Internationalization
All user-facing strings SHALL be internationalized with at least English and Spanish translations.

#### Scenario: English locale
- **WHEN** the app language is English
- **THEN** all epistemic analytics text renders in English

#### Scenario: Spanish locale
- **WHEN** the app language is Spanish
- **THEN** all epistemic analytics text renders in Spanish
