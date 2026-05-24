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

#### Scenario: Empty-state banner guides the user
- **WHEN** a screen has no data and shows an empty state
- **THEN** the empty-state banner provides guidance, next action, and stakeholder context
- **AND** turns the blank state into a guided action rather than a dead end

#### Scenario: Feature announcement banner introduces a new capability
- **WHEN** a new capability is released
- **THEN** a feature announcement banner can introduce it without interrupting the user workflow
- **AND** the banner can be dismissed or collapsed

#### Scenario: AI-assisted banner explains AI involvement
- **WHEN** a banner describes AI-assisted analysis or generated narrative
- **THEN** it discloses AI involvement where stakeholder trust depends on it
- **AND** points to evidence, confidence, or review state when available

#### Scenario: Stakeholder banner frames audience context
- **WHEN** a dashboard or report is presented for a specific stakeholder audience
- **THEN** a stakeholder banner frames the content for that audience
- **AND** shows the audience preset and relevant decision context

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

#### Scenario: AI-generated imagery is appropriate
- **WHEN** a banner includes AI-generated imagery
- **THEN** the imagery is appropriate for scientific intelligence contexts
- **AND** does not imply false evidence or misleading data visualizations

### Requirement: Banner usage is governed by narrative purpose
UKIP SHALL require banners to serve a clear product narrative purpose rather than decorative filler.

#### Scenario: Feature team proposes a new banner
- **WHEN** a new banner is introduced
- **THEN** the implementation declares whether the banner is for orientation, evidence framing, stakeholder positioning, empty-state guidance, report packaging, or AI disclosure
- **AND** the banner can be hidden, collapsed, or replaced by a compact summary when repeated-use workflows require density

#### Scenario: Banner content includes structured elements
- **WHEN** a banner contains content
- **THEN** it may include title, supporting copy, primary/secondary action, short metrics, provenance/evidence tags, media, audience label, and confidence or review status
- **AND** each element serves the declared narrative purpose

#### Scenario: Banner does not push core controls below the fold
- **WHEN** a banner appears on a screen with primary task controls
- **THEN** the banner does not push those controls below the fold without a strong justified reason
- **AND** the banner supports collapse or compact mode for repeated-use scenarios
