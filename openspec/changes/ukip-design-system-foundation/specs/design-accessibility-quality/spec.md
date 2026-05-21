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

### Requirement: Design QA catches visual regressions
UKIP SHALL validate high-impact UI changes for layout, contrast, responsiveness, and text overflow.

#### Scenario: Dashboard widget is changed
- **WHEN** a dashboard widget layout changes
- **THEN** the change is checked for desktop and mobile readability
- **AND** long translated text must not overlap controls or adjacent content

#### Scenario: Control target is too cramped
- **WHEN** a switch, button, tab, or icon control is difficult to interact with
- **THEN** the control should be revised for spacing, hit area, and visual affordance
