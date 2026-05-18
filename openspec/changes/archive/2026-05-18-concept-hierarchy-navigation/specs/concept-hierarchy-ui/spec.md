## ADDED Requirements

### Requirement: Concept hierarchy page accessible from navigation
The system SHALL provide a page at `/analytics/concepts` accessible from the sidebar navigation under the Analytics section, visible to all authenticated users.

#### Scenario: Page accessible from sidebar
- **WHEN** authenticated user clicks "Concept Hierarchy" in the Analytics sidebar section
- **THEN** the browser navigates to `/analytics/concepts`
- **THEN** the page renders with a title and the concept tree visualization

#### Scenario: Page shows empty state when no concepts materialized
- **WHEN** user navigates to /analytics/concepts
- **AND** no concept_nodes exist for the active domain
- **THEN** the page shows an empty state message with a prompt for admins to trigger materialization

### Requirement: Interactive tree view displays concept hierarchy
The system SHALL render a collapsible tree view as the default visualization, showing concept nodes with their display names, levels, and entity counts.

#### Scenario: Tree renders with expandable nodes
- **WHEN** the concept tree loads with data
- **THEN** level-0 and level-1 nodes are expanded by default
- **THEN** level-2+ nodes are collapsed by default
- **THEN** each node shows its name and entity count badge

#### Scenario: User expands a collapsed node
- **WHEN** user clicks the expand arrow on a collapsed node
- **THEN** its children become visible with smooth animation

#### Scenario: User collapses an expanded node
- **WHEN** user clicks the collapse arrow on an expanded node
- **THEN** its children and all descendants are hidden

### Requirement: Sunburst visualization toggle
The system SHALL offer a toggle to switch between tree view and sunburst (radial treemap) visualization, showing proportional entity distribution across the concept hierarchy.

#### Scenario: Toggle to sunburst view
- **WHEN** user clicks the "Sunburst" toggle button
- **THEN** the tree view is replaced by a radial sunburst chart
- **THEN** each ring level corresponds to a concept hierarchy level
- **THEN** segment size is proportional to entity_count

#### Scenario: Toggle back to tree view
- **WHEN** user is in sunburst view and clicks "Tree" toggle button
- **THEN** the sunburst is replaced by the collapsible tree view

### Requirement: Clicking a concept node navigates to filtered entity list
The system SHALL allow users to click on a concept node (in either view) to navigate to the entity table filtered by that concept.

#### Scenario: Click concept in tree view
- **WHEN** user clicks a concept node name in the tree view
- **THEN** the browser navigates to the entity table with a filter applied for that concept (e.g., `/entities?concept=Machine+Learning`)

#### Scenario: Click segment in sunburst view
- **WHEN** user clicks a segment in the sunburst chart
- **THEN** the browser navigates to the entity table with the corresponding concept filter applied

### Requirement: Concept detail panel on hover/focus
The system SHALL show a tooltip or detail panel when hovering over a concept node, displaying: full concept name, level, entity count, and parent concept name.

#### Scenario: Hover shows concept details
- **WHEN** user hovers over a concept node in the tree view
- **THEN** a tooltip appears showing: concept name, level number, entity count, and parent concept name (or "Root" for level-0)

#### Scenario: Hover on sunburst segment
- **WHEN** user hovers over a sunburst segment
- **THEN** a tooltip appears with the same detail information

### Requirement: Admin materialization trigger from UI
The system SHALL show a "Refresh Hierarchy" button (visible only to admin+ users) that triggers the materialization endpoint and shows progress feedback.

#### Scenario: Admin sees refresh button
- **WHEN** an admin user views /analytics/concepts
- **THEN** a "Refresh Hierarchy" button is visible

#### Scenario: Viewer does not see refresh button
- **WHEN** a viewer user views /analytics/concepts
- **THEN** no "Refresh Hierarchy" button is shown

#### Scenario: Clicking refresh triggers materialization
- **WHEN** admin clicks "Refresh Hierarchy"
- **THEN** the system calls POST /analytics/concepts/{domain_id}/materialize
- **THEN** a loading indicator is shown during processing
- **THEN** on success, the tree view reloads with updated data and a success toast appears

### Requirement: Internationalization support
The system SHALL use the existing i18n system for all UI strings on the concept hierarchy page, supporting at minimum English and Spanish.

#### Scenario: Page renders in Spanish
- **WHEN** user has language set to "es"
- **AND** navigates to /analytics/concepts
- **THEN** all labels, buttons, and messages render in Spanish

#### Scenario: Page renders in English
- **WHEN** user has language set to "en"
- **AND** navigates to /analytics/concepts
- **THEN** all labels, buttons, and messages render in English
