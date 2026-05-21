## ADDED Requirements

### Requirement: UKIP governs design tokens semantically
UKIP SHALL define and use design tokens according to semantic product roles rather than ad hoc visual preference.

#### Scenario: New color token is introduced
- **WHEN** a frontend change introduces a new color token
- **THEN** the token declares whether it supports brand, intelligence, evidence, caution, risk, neutral surface, text, border, or focus semantics
- **AND** the token includes light and dark mode behavior when applicable

#### Scenario: Existing component uses hardcoded colors
- **WHEN** a reusable component uses hardcoded visual colors for semantic state
- **THEN** the component should migrate toward UKIP design tokens or documented Tailwind semantic equivalents

### Requirement: Light mode remains the default experience
UKIP SHALL keep light mode as the default visual experience regardless of system preference.

#### Scenario: User opens UKIP in a new browser
- **WHEN** there is no explicit stored theme preference
- **THEN** UKIP loads in light mode
- **AND** does not automatically adopt the operating system dark preference
