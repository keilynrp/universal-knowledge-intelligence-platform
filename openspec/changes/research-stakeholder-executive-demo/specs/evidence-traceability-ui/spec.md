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

### Requirement: Missing evidence is explicit
The UI SHALL not hide missing evidence. If evidence cannot be resolved, it SHALL show a concise limitation note.

#### Scenario: Evidence reference cannot be resolved
- **WHEN** an evidence reference points to unavailable data
- **THEN** the UI shows a fallback limitation message instead of failing silently
