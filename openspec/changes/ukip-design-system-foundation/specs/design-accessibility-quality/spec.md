## ADDED Requirements

### Requirement: UKIP design components meet accessibility expectations
UKIP SHALL ensure governed components support keyboard interaction, visible focus states, readable contrast, and accessible labels.

#### Scenario: Interactive control is rendered
- **WHEN** a button, link, select, switch, tab, or menu item is rendered
- **THEN** it has a visible focus state
- **AND** supports keyboard operation appropriate to its role

#### Scenario: Semantic state uses color
- **WHEN** color indicates evidence, warning, risk, confidence, or completion
- **THEN** the UI also provides text, iconography, label, or structure so meaning is not conveyed by color alone

#### Scenario: Focus ring is visible in light and dark modes
- **WHEN** a control receives keyboard focus
- **THEN** the focus ring is visible and meets contrast requirements in both light and dark modes

#### Scenario: Interactive control has adequate touch target
- **WHEN** a switch, button, tab, or icon control is rendered
- **THEN** the touch target meets minimum size requirements (at least 44x44 CSS pixels for primary actions)

### Requirement: Design QA catches visual regressions
UKIP SHALL validate high-impact UI changes for layout, contrast, responsiveness, and text overflow.

#### Scenario: Dashboard widget is changed
- **WHEN** a dashboard widget layout changes
- **THEN** the change is checked for desktop and mobile readability
- **AND** long translated text must not overlap controls or adjacent content

#### Scenario: Control target is too cramped
- **WHEN** a switch, button, tab, or icon control is difficult to interact with
- **THEN** the control should be revised for spacing, hit area, and visual affordance

#### Scenario: Contrast meets requirements in both themes
- **WHEN** semantic state colors are used in light and dark modes
- **THEN** text over colored backgrounds meets WCAG AA contrast ratio (4.5:1 for normal text, 3:1 for large text)

#### Scenario: Responsive layout is tested at key breakpoints
- **WHEN** a layout change is made to dashboards, tables, cards, or sidebars
- **THEN** it is verified at mobile (320px), tablet (768px), and desktop (1024px, 1440px) viewports

#### Scenario: Text overflow is checked for translated content
- **WHEN** buttons, badges, cards, panels, or table cells display text
- **THEN** the text does not overflow its container when rendered in the longest supported locale

### Requirement: Media accessibility is enforced for banners and visual content
UKIP SHALL ensure banner media and visual content meet accessibility requirements.

#### Scenario: Informative image has alt text
- **WHEN** a banner or visual component includes an informative image
- **THEN** the image has descriptive alt text

#### Scenario: Decorative image is marked appropriately
- **WHEN** a banner includes a purely decorative image
- **THEN** the image is marked with empty alt text or role=presentation

#### Scenario: Motion respects reduced-motion preference
- **WHEN** a banner or component includes animation
- **THEN** the motion is suppressed when the user has enabled reduced-motion preferences

### Requirement: Visual QA checklist is applied to frontend PRs
UKIP SHALL apply a visual QA checklist to frontend pull requests that modify governed components.

#### Scenario: Frontend PR modifies a governed component
- **WHEN** a PR modifies a button, KPI card, data table, badge, panel, or banner component
- **THEN** the reviewer verifies layout stability, contrast, responsive behavior, text overflow, focus visibility, and touch target adequacy
