## ADDED Requirements

### Requirement: UKIP supports governed visual banner patterns
UKIP SHALL define visual banner patterns for narrative, onboarding, stakeholder framing, evidence journeys, reports, and empty states.

#### Scenario: Onboarding banner is shown
- **WHEN** a user enters a workflow for the first time or starts a pilot journey
- **THEN** the banner explains the purpose, next action, and stakeholder value
- **AND** includes only media that helps users understand the workflow or expected outcome

#### Scenario: Dashboard narrative banner is shown
- **WHEN** a dashboard needs to frame current readiness, evidence gaps, or strategic context
- **THEN** the banner links visual treatment to the underlying data state
- **AND** does not obscure the primary dashboard controls or metrics

#### Scenario: Report cover banner is generated
- **WHEN** UKIP creates a stakeholder-facing report
- **THEN** the report may include a visual cover banner that reflects audience, domain, evidence readiness, and report purpose
- **AND** avoids implying conclusions that are not supported by the report evidence

### Requirement: Banner media is meaningful, accessible, and responsive
Banner visuals SHALL be relevant, accessible, responsive, and safe for scientific intelligence contexts.

#### Scenario: Banner uses an image or generated visual
- **WHEN** a banner includes an image, generated bitmap, illustration, screenshot, or background media
- **THEN** the media relates to the product, workflow, evidence, dataset, or stakeholder context
- **AND** includes alt text when informative or is marked decorative when not informative

#### Scenario: Banner includes motion
- **WHEN** a banner uses animation or video
- **THEN** the motion is subtle, non-blocking, and respects reduced-motion preferences
- **AND** the banner remains understandable without motion

#### Scenario: Banner text overlays media
- **WHEN** text appears over or beside media
- **THEN** the text maintains readable contrast across supported viewport sizes
- **AND** responsive cropping does not hide essential media context

### Requirement: Banner usage is governed by narrative purpose
UKIP SHALL require banners to serve a clear product narrative purpose rather than decorative filler.

#### Scenario: Feature team proposes a new banner
- **WHEN** a new banner is introduced
- **THEN** the implementation declares whether the banner is for orientation, evidence framing, stakeholder positioning, empty-state guidance, report packaging, or AI disclosure
- **AND** the banner can be hidden, collapsed, or replaced by a compact summary when repeated-use workflows require density

#### Scenario: AI-assisted banner is used
- **WHEN** a banner describes AI-assisted analysis or generated narrative
- **THEN** it discloses AI involvement where stakeholder trust depends on it
- **AND** points to evidence, confidence, or review state when available
