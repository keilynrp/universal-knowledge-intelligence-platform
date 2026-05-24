## ADDED Requirements

### Requirement: Recommendations expose supporting evidence
Each executive recommendation SHALL expose evidence references that explain why the recommendation was produced.

#### Scenario: Recommendation has benchmark evidence
- **WHEN** a recommendation is driven by an institutional benchmark gap
- **THEN** the UI shows the benchmark rule, observed value, threshold, and message

#### Scenario: Recommendation has concept evidence
- **WHEN** a recommendation is driven by concept, topic, or semantic keyword signals
- **THEN** the UI shows the supporting concept labels, counts, and relevant dashboard section link

#### Scenario: Recommendation has entity evidence
- **WHEN** a recommendation is driven by specific records or record filters
- **THEN** the UI links to the corresponding entity list or filtered explorer view

#### Scenario: Recommendation has quality evidence
- **WHEN** a recommendation is driven by quality score gaps
- **THEN** the UI shows the quality threshold, observed value, and the entity filter for low-quality records

#### Scenario: Recommendation has enrichment coverage evidence
- **WHEN** a recommendation is driven by enrichment coverage gaps
- **THEN** the UI shows the enrichment coverage percentage and the action to improve it

### Requirement: Missing evidence is explicit
The UI SHALL not hide missing evidence. If evidence cannot be resolved, it SHALL show a concise limitation note.

#### Scenario: Evidence reference cannot be resolved
- **WHEN** an evidence reference points to unavailable data
- **THEN** the UI shows a fallback limitation message instead of failing silently

#### Scenario: Evidence is partially available
- **WHEN** some evidence references resolve but others do not
- **THEN** the UI shows available evidence and marks missing references with limitation copy

### Requirement: Evidence panels are expandable
UKIP SHALL provide expandable evidence panels that link to supporting records, benchmark rules, concepts, quality filters, and sources.

#### Scenario: Evidence panel expands to show detail
- **WHEN** the user clicks on a compact evidence reference
- **THEN** an expandable panel reveals the full evidence detail including source references, values, and links

#### Scenario: Evidence panel links to source records
- **WHEN** evidence references specific entities or records
- **THEN** the panel includes links to the entity detail or filtered entity list

#### Scenario: Evidence panel links to benchmark rules
- **WHEN** evidence references benchmark rules
- **THEN** the panel includes the rule name, threshold, and observed value

### Requirement: Evidence interaction is tracked
UKIP SHALL track evidence panel interactions via the existing frontend analytics helper.

#### Scenario: Evidence panel open is tracked
- **WHEN** a user expands an evidence panel
- **THEN** the interaction is recorded via the frontend analytics helper with the evidence type and context

### Requirement: Evidence traceability carries into exported briefs
UKIP SHALL include evidence references in exported PDF/HTML briefs.

#### Scenario: Exported brief includes evidence appendix
- **WHEN** a stakeholder brief is exported
- **THEN** the export includes an evidence appendix section listing the supporting evidence for each recommendation

#### Scenario: Evidence appendix preserves dashboard evidence
- **WHEN** the evidence appendix is generated
- **THEN** it preserves the same evidence references, benchmark rules, concept sources, and quality thresholds shown in the dashboard

#### Scenario: Exported brief preserves recommendation consistency
- **WHEN** a stakeholder brief is exported
- **THEN** the recommendations, confidence, gaps, and evidence in the export match what was shown in the dashboard at export time

### Requirement: Evidence fallback copy is graceful
UKIP SHALL provide graceful fallback copy when evidence is unavailable or incomplete.

#### Scenario: No evidence is available for a recommendation
- **WHEN** a recommendation has no resolvable evidence references
- **THEN** the UI shows a concise message indicating that evidence is not available for this recommendation
- **AND** the recommendation is de-emphasized compared to evidence-backed recommendations

#### Scenario: Evidence unavailable in export
- **WHEN** an exported brief includes a recommendation without resolvable evidence
- **THEN** the evidence appendix notes the limitation for that recommendation
