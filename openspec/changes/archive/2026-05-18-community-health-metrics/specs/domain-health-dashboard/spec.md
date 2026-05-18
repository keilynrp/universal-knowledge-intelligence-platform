## ADDED Requirements

### Requirement: Domain health dashboard page
The system SHALL provide a dedicated page at `/analytics/domain-health` displaying community health metrics for the active domain. The page SHALL follow the existing analytics page pattern (header, loading skeleton, empty state, data view).

#### Scenario: Page loads with health data
- **WHEN** a user navigates to `/analytics/domain-health` and the active domain has discourse_community config
- **THEN** the page SHALL display 5 metric cards with current values and trend sparklines

#### Scenario: Domain without config shows informative state
- **WHEN** the active domain lacks discourse_community configuration
- **THEN** the page SHALL display a "not configured" message consistent with the epistemic analysis page pattern

#### Scenario: Loading state
- **WHEN** the page is fetching data
- **THEN** the page SHALL display animated skeleton placeholders

### Requirement: Health metric indicator cards
Each metric SHALL be displayed as a card showing: the metric name, current aggregate value (formatted as percentage or decimal), an interpretation label (e.g., "Low concentration", "High diversity"), and a color-coded indicator (green=healthy, amber=moderate, red=concerning).

#### Scenario: Gini card display
- **WHEN** the Gini coefficient is 0.35
- **THEN** the card SHALL show "0.35", label "Moderate concentration", and amber indicator

#### Scenario: Metric unavailable
- **WHEN** a metric value is `null` (insufficient data)
- **THEN** the card SHALL show "N/A" with a tooltip explaining why the metric is unavailable

### Requirement: Temporal trend visualization
The page SHALL include a line chart showing metric evolution over years. Users SHALL be able to toggle which metrics are visible on the chart.

#### Scenario: Multi-year trend display
- **WHEN** the domain has data spanning 5+ years
- **THEN** the chart SHALL display lines for each selected metric with year on the x-axis and value on the y-axis

#### Scenario: Single year of data
- **WHEN** the domain has entities from only 1 year
- **THEN** the trend chart SHALL be hidden and a message SHALL indicate insufficient temporal data

### Requirement: Cross-domain comparison
The page SHALL allow selecting a second domain for side-by-side metric comparison. Both domains' metrics SHALL be displayed in a comparison view.

#### Scenario: Two domains compared
- **WHEN** the user selects a second domain from the comparison dropdown
- **THEN** the page SHALL display metric cards for both domains side-by-side with difference indicators

#### Scenario: Comparison domain lacks config
- **WHEN** the selected comparison domain lacks discourse_community config
- **THEN** the system SHALL show a message that the comparison domain has no community metrics

### Requirement: Sidebar navigation entry
The sidebar SHALL include a "Domain Health" navigation item under the analytics section, linking to `/analytics/domain-health`.

#### Scenario: Navigation item visible
- **WHEN** any authenticated user views the sidebar
- **THEN** "Domain Health" SHALL appear in the analytics navigation group with an appropriate icon

### Requirement: Internationalization support
All UI strings (metric names, labels, interpretation text, empty states) SHALL use the i18n translation system with keys under the `domain_health` namespace. Both EN and ES translations SHALL be provided.

#### Scenario: English locale
- **WHEN** the app language is set to English
- **THEN** all domain health strings SHALL display in English

#### Scenario: Spanish locale
- **WHEN** the app language is set to Spanish
- **THEN** all domain health strings SHALL display in Spanish

### Requirement: Admin-only actions are not required
The domain health dashboard is read-only analytics. No admin-only actions (like classify or configure) are needed on this page. All authenticated users SHALL have access.

#### Scenario: Viewer can access dashboard
- **WHEN** a viewer-role user navigates to `/analytics/domain-health`
- **THEN** the page SHALL load and display metrics without restrictions
