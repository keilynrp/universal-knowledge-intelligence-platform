## ADDED Requirements

### Requirement: Evidence and provenance states have consistent visual semantics
UKIP SHALL define consistent visual treatment for source, canonical, enrichment, authority, review, audit, and confidence states.

#### Scenario: Entity detail shows layered data
- **WHEN** original source, canonical identity, enrichment observation, and authority link values are shown together
- **THEN** the UI visually distinguishes each layer
- **AND** uses consistent labels, badges, or section treatments across entity detail and reports

#### Scenario: Mapping suggestion needs review
- **WHEN** a mapping suggestion has low confidence or conflicting evidence
- **THEN** the UI marks it as review-required
- **AND** avoids presenting it as canonical truth

### Requirement: AI-generated or AI-assisted content is disclosed when trust depends on it
UKIP SHALL disclose AI-assisted content when users may rely on it for decisions.

#### Scenario: AI generates executive narrative
- **WHEN** an executive narrative includes AI-generated or AI-assisted text
- **THEN** the UI indicates AI involvement and evidence grounding or review status

#### Scenario: AI suggests an entity match
- **WHEN** AI suggests a canonical entity or authority match
- **THEN** the UI presents the result as a candidate unless governed resolution or review promotes it
