## ADDED Requirements

### Requirement: Reads that matter are audited by class

The system SHALL write an audit row for an authenticated `GET` or `HEAD`
request when it falls in one of these classes, and SHALL NOT write one
otherwise:

1. its route is in the export table (`EXPORT`);
2. its route is under `/audit-log` (`READ`);
3. it was authenticated with an API key (`READ`);
4. it requests a page past the first (`skip > 0`) or more than 500 rows
   (`READ`).

#### Scenario: An export records its own execution

- **WHEN** an admin downloads `GET /audit-log/export`
- **THEN** an audit row with action `EXPORT` and that route is written

#### Scenario: A pagination sweep is recorded

- **WHEN** an authenticated JWT client requests `GET /entities?skip=100&limit=100`
- **THEN** an audit row with action `READ`, the client's `session_id`, and
  `details.skip = 100` is written

#### Scenario: Ordinary browsing is not recorded

- **WHEN** an authenticated JWT client requests `GET /entities?limit=500`
- **THEN** no audit row is written for that request

#### Scenario: Every API key read is recorded

- **WHEN** a request authenticated with an API key reads `GET /entities`
- **THEN** an audit row with action `READ` and that key's `api_key_id` is
  written

#### Scenario: Anonymous reads are not audited

- **WHEN** an unauthenticated request reads a public endpoint
- **THEN** no audit row is written

### Requirement: Read audit rows never record query values

The system SHALL record, for an audited read, the route template, the status
code, the principal, `limit`, `skip`, and the **names** of the query
parameters, and SHALL NOT record any other query value.

#### Scenario: A search term is not stored

- **WHEN** an audited read carries `?q=jane%20doe&skip=50`
- **THEN** the row's details contain `skip = 50` and `query_keys = ["q", "skip"]`
- **AND** the string `jane` appears nowhere in the row

### Requirement: Export routes cannot land unaudited

The system SHALL fail its test suite when a `GET` route whose template
contains `export`, `download` or `csv`, or which returns a streaming file
response, is neither in the export table nor on the documented exclusion list.

#### Scenario: New export route without classification

- **WHEN** a router adds `GET /widgets/export` and does not add it to the table
- **THEN** the route-coverage test fails and names the route

### Requirement: The audit log pivots on a session

The system SHALL accept `session_id` as an exact-match filter on
`GET /audit-log`, `GET /audit-log/export` and `GET /audit-log/stats`, and SHALL
accept `READ` and `EXPORT` as values of the action filter.

#### Scenario: Everything one session did

- **WHEN** an admin requests `GET /audit-log?session_id=<sid>`
- **THEN** only rows written for requests authenticated by that session are
  returned, reads and mutations alike
