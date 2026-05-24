## ADDED Requirements

### Requirement: Entity detail separates data provenance layers
The entity detail view SHALL separate fields into original ingestion data, UKIP normalized identity, external enrichment, and authority/audit sections.

#### Scenario: Entity has original and enriched data
- **WHEN** an entity includes both ingestion fields and enrichment fields
- **THEN** original ingestion fields appear in an "Original ingestion" section
- **AND** enrichment fields appear in an "External enrichment" section

#### Scenario: Entity has normalized fields
- **WHEN** an entity has `primary_label`, `canonical_id`, `entity_type`, or validation fields
- **THEN** those fields appear in a "UKIP normalized identity" section

#### Scenario: Entity has authority records
- **WHEN** an entity has linked authority records with resolver source and confidence
- **THEN** those records appear in an "Authority and audit" section
- **AND** the section includes timestamps, review status, and resolver provenance

#### Scenario: Entity has only ingestion data
- **WHEN** an entity has been ingested but not enriched or authority-resolved
- **THEN** the "External enrichment" and "Authority and audit" sections indicate their empty state with appropriate null reasons
- **AND** the "Original ingestion" and "UKIP normalized identity" sections render available fields

### Requirement: Entity detail preserves original imported values
The entity detail view SHALL preserve original imported values separately from normalized and enriched values.

#### Scenario: Original SKU differs from enriched DOI
- **WHEN** an original record includes SKU and enrichment resolves DOI
- **THEN** SKU is shown as an original identifier
- **AND** DOI is shown as an enrichment identifier

#### Scenario: Original label differs from normalized label
- **WHEN** the original source provides a label and UKIP normalizes it to a different `primary_label`
- **THEN** both the original source label and the normalized `primary_label` are visible
- **AND** each appears in its respective provenance section

#### Scenario: Re-ingestion updates source layer without overwriting normalized identity
- **WHEN** the same source record is re-ingested with updated values
- **THEN** the original ingestion section reflects the latest source values
- **AND** the UKIP normalized identity section is not silently overwritten

### Requirement: Entity detail payload maps fields to provenance layers
UKIP SHALL define a field inventory that maps every entity detail field to exactly one provenance layer.

#### Scenario: Field inventory covers all entity detail fields
- **WHEN** the entity detail payload includes any field from the RawEntity model
- **THEN** a grouping helper assigns the field to one of: original_ingestion, normalized_identity, external_enrichment, or authority_audit

#### Scenario: Frontend types define layer and field structure
- **WHEN** the frontend renders entity detail
- **THEN** it uses `EntityDetailLayer` and `EntityDetailField` types to organize the display
- **AND** each field carries a layer identifier, display label, value, and optional null-reason

#### Scenario: Grouping is consistent across uploaded, demo, and OpenAlex-enriched records
- **WHEN** entity records come from different ingestion sources (user upload, demo seed, API connector)
- **THEN** the same grouping helper assigns their fields to the correct provenance layers
- **AND** tests verify grouping for representative records of each ingestion type

### Requirement: Entity detail UI renders provenance sections with visual distinction
The entity detail page SHALL render provenance layers as visually distinct sections with provenance badges.

#### Scenario: Entity detail page renders four sections
- **WHEN** the entity detail page loads
- **THEN** it renders sections for Original Ingestion, UKIP Normalized Identity, External Enrichment, and Authority and Audit
- **AND** each section has a heading and visual boundary

#### Scenario: Scientific affiliations render under external enrichment
- **WHEN** an entity has structured scientific affiliations from an enrichment provider
- **THEN** they appear within the External Enrichment section
- **AND** they are not mixed with original ingestion affiliation text

#### Scenario: Provenance badges distinguish field origins
- **WHEN** the entity detail page displays a field
- **THEN** the field carries a compact provenance badge indicating its layer (original, normalized, enrichment, or authority)
- **AND** the badge is consistent across all entity types and domains

### Requirement: Backend serializer supports layered entity detail
UKIP SHALL evaluate and, when needed, provide a backend serializer that structures entity detail into provenance layers.

#### Scenario: Current entity detail payload exposes import batch metadata
- **WHEN** the entity detail endpoint is called
- **THEN** the response includes import batch identifier, source connector type, and original field metadata when available

#### Scenario: Backend serializer produces layered detail metadata
- **WHEN** the backend introduces a layered detail serializer
- **THEN** the serializer groups entity fields into the four provenance layers
- **AND** each field includes its display label, value, and null-reason code

#### Scenario: Serializer preserves backwards-compatible fields
- **WHEN** a layered detail serializer is introduced
- **THEN** existing entity detail consumers continue to receive all fields they previously received
- **AND** the layered structure is an additive overlay, not a breaking replacement

#### Scenario: API tests validate serializer output
- **WHEN** a backend serializer is introduced
- **THEN** API tests verify that representative entity payloads produce the correct layer assignments and null-reason codes
