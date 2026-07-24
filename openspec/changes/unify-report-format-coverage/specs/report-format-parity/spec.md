## ADDED Requirements

### Requirement: Every selectable section is available in every export format

The system SHALL render each section returned by `GET /reports/sections` in
every export format, or explicitly declare that format cannot represent it.
Silent omission SHALL NOT occur.

#### Scenario: A selected section reaches every format

- **WHEN** a report is requested in HTML, PDF, Excel and PPTX with the same
  section list
- **THEN** each output contains a recognizable representation of every
  requested section, except those the format has declared unsupported

#### Scenario: Section registry and format coverage cannot drift apart

- **WHEN** a new section is added to the section registry
- **AND** no renderer declares it supported or unsupported
- **THEN** the parity test fails

#### Scenario: Unsupported sections are reported, not dropped

- **WHEN** a requested section is declared unsupported by the requested format
- **THEN** the response identifies the omitted sections to the caller
- **AND** the remaining requested sections still render

### Requirement: Section data is format-neutral

The system SHALL separate section data collection from section presentation, so
each section is authored once and rendered by every format.

#### Scenario: Collection is reusable without HTML

- **WHEN** a section's collector is invoked
- **THEN** it returns a structured payload containing no markup

#### Scenario: Renderers consume only the payload

- **WHEN** a format renderer produces output for a section
- **THEN** it derives that output solely from the section payload, without
  issuing its own entity or harmonization queries

#### Scenario: Migration preserves existing HTML sections

- **WHEN** a section is migrated from a direct HTML builder to the
  collector-plus-renderer path
- **THEN** the section's existing rendering tests still pass

### Requirement: Export endpoints validate section names consistently

The system SHALL apply the same unknown-section validation to every export
endpoint.

#### Scenario: Excel rejects unknown sections

- **WHEN** `POST /exports/excel` is called with a section name that is not in
  the section registry
- **THEN** the response is 422
- **AND** the detail lists the valid section names

#### Scenario: Deprecated aliases resolve before rendering

- **WHEN** a section is requested by the public id that `GET /reports/sections`
  returns
- **THEN** every format renders it, regardless of any deprecated alias the
  section also answers to

#### Scenario: All export endpoints agree on validity

- **WHEN** the same unknown section name is sent to the HTML, PDF, Excel and
  PPTX endpoints
- **THEN** all four reject it with 422

### Requirement: Per-format availability is discoverable before export

The system SHALL expose which formats can render each section, so a caller can
see availability before requesting an export.

#### Scenario: The section listing carries format availability

- **WHEN** `GET /reports/sections` is requested
- **THEN** each section entry states which export formats support it

#### Scenario: Scheduled reports do not silently under-deliver

- **WHEN** a scheduled report is configured with sections its format cannot
  render
- **THEN** the omission is recorded on the run rather than passing as a clean
  delivery
