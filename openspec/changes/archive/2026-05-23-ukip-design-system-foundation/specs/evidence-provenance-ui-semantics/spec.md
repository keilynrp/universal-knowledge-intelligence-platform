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

#### Scenario: Provenance badge is consistent across surfaces
- **WHEN** a provenance badge (source, canonical, enrichment, authority) appears on entity detail, reports, reconciliation review, or dashboards
- **THEN** the badge uses the same visual treatment (color, label, icon) regardless of which surface renders it

#### Scenario: Confidence indicator covers all levels
- **WHEN** a confidence indicator is displayed
- **THEN** it distinguishes high, medium, low, unknown, and review-required confidence levels
- **AND** uses both color and text/icon so meaning is not conveyed by color alone

#### Scenario: Null-state visual treatment matches provenance semantics
- **WHEN** a field shows a null-reason code (not-provided, pending-normalization, unresolved-enrichment, not-applicable, unknown)
- **THEN** the visual treatment is consistent with the evidence-provenance semantic system
- **AND** is visually de-emphasized compared to populated fields

### Requirement: AI-generated or AI-assisted content is disclosed when trust depends on it
UKIP SHALL disclose AI-assisted content when users may rely on it for decisions.

#### Scenario: AI generates executive narrative
- **WHEN** an executive narrative includes AI-generated or AI-assisted text
- **THEN** the UI indicates AI involvement and evidence grounding or review status

#### Scenario: AI suggests an entity match
- **WHEN** AI suggests a canonical entity or authority match
- **THEN** the UI presents the result as a candidate unless governed resolution or review promotes it

#### Scenario: AI-assisted indicator is visually distinct
- **WHEN** AI-assisted or AI-generated content is displayed
- **THEN** the disclosure indicator uses a consistent visual treatment across all surfaces (reports, dashboards, entity detail, RAG responses)
- **AND** the indicator distinguishes between ai-assisted (human-in-the-loop) and ai-generated (fully automated)

### Requirement: Trust-state semantics are applied consistently across product surfaces
UKIP SHALL apply evidence and trust-state visual semantics consistently to entity detail, reports, reconciliation review, dashboards, and AI-generated narratives.

#### Scenario: Entity detail applies trust-state semantics
- **WHEN** entity detail renders provenance layers
- **THEN** it uses the governed provenance badge, confidence indicator, and null-state treatment

#### Scenario: Reports apply trust-state semantics
- **WHEN** a report presents claims with evidence layers
- **THEN** it uses the governed provenance and confidence visual treatments

#### Scenario: Dashboard applies trust-state semantics
- **WHEN** a dashboard widget shows authority coverage or enrichment readiness
- **THEN** it uses the governed semantic color and badge treatments
