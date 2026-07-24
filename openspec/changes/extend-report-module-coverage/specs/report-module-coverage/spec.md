## ADDED Requirements

### Requirement: Reports surface authority control status

The system SHALL provide a report section describing identity-resolution state,
so a reader can judge how settled the underlying records are.

#### Scenario: Authority section reports resolution state

- **WHEN** a report is generated with the authority control section and
  authority records exist
- **THEN** the section reports total, confirmed and pending-review counts
- **AND** reports the distribution across resolution statuses

#### Scenario: Unresolved conflicts are visible

- **WHEN** authority records require human review
- **THEN** the section lists the highest-impact unresolved conflicts with their
  confidence

#### Scenario: Authority backlog is stated in prose

- **WHEN** a review backlog exists
- **THEN** the section states in prose what that backlog means for the
  reliability of the report

#### Scenario: Empty state is explanatory

- **WHEN** no authority records exist
- **THEN** the section explains that authority resolution has not run, rather
  than reporting zero conflicts as a finding

### Requirement: Readiness language accounts for the authority backlog

The system SHALL prevent a report from presenting a confident readiness stance
while a material identity-resolution backlog is unaddressed.

#### Scenario: Material backlog qualifies the stakeholder reading

- **WHEN** pending authority records are material relative to total entities
- **THEN** the stakeholder reading states the backlog as a confidence caveat

#### Scenario: The observed ratio is always disclosed

- **WHEN** the stakeholder reading is rendered
- **THEN** it reports the observed pending-to-total ratio, whether or not the
  materiality threshold was crossed

#### Scenario: Immaterial backlog does not raise a caveat

- **WHEN** pending authority records are below the materiality threshold
- **THEN** no backlog caveat is raised

### Requirement: Reports surface the collaboration graph

The system SHALL provide a report section describing the coauthorship structure.

#### Scenario: Graph section reports structure

- **WHEN** a report is generated with the collaboration section and author
  statistics exist
- **THEN** the section reports author count, edge count and community count
- **AND** lists the most central authors with degree, centrality and
  publication count

#### Scenario: Bridge authors are identified

- **WHEN** authors connect otherwise separate communities
- **THEN** the section identifies them

#### Scenario: Report generation does not recompute the graph

- **WHEN** the collaboration section is rendered
- **THEN** it reads precomputed author statistics and does not execute graph
  computation

#### Scenario: Stale statistics are disclosed

- **WHEN** author statistics carry no computation timestamp, or one that is
  stale
- **THEN** the section discloses this instead of presenting the values as
  current

### Requirement: Reports surface the journal portfolio

The system SHALL provide a report section describing where the portfolio is
published, at what open-access cost, and with what field-normalized standing.

#### Scenario: Journal section reports the portfolio

- **WHEN** a report is generated with the journal section and journal metrics
  exist
- **THEN** the section reports distinct journal count, DOAJ share and APC
  exposure
- **AND** lists top journals by publication count

#### Scenario: Bayesian estimates always carry their interval

- **WHEN** a Bayesian normalized impact estimate is rendered
- **THEN** its credible interval is rendered with it

#### Scenario: Normalized impact is not labelled as impact factor

- **WHEN** the normalized impact figure is rendered
- **THEN** it is labelled as a field-normalized open proxy
- **AND** it is not labelled as a Journal Impact Factor

#### Scenario: Local coverage counts are labelled as local

- **WHEN** a locally derived two-year works count is rendered
- **THEN** it is labelled as local coverage rather than a global count

### Requirement: New sections honor tenant isolation

The system SHALL scope every new report section to the requesting
organization.

#### Scenario: Sections exclude other organizations' data

- **WHEN** any new section is rendered for an organization
- **THEN** it contains no authority record, author or journal metric belonging
  to another organization

### Requirement: New sections are available in every export format

The system SHALL make each new section available in every export format, under
the established format-parity contract.

#### Scenario: New sections satisfy the parity contract

- **WHEN** the format parity test enumerates the section registry
- **THEN** each new section renders in every format, or is explicitly declared
  unsupported by that format
