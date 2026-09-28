## ADDED Requirements

### Requirement: Request and proxy logs outlive the container

The system SHALL copy the backend's request log and the proxy's access log off
the host as they are written, so that recreating a container, including by a
deploy, does not remove log lines that were already written.

#### Scenario: A deploy happens during an incident

- **WHEN** a request is logged by `ukip-backend`
- **AND** the container is then recreated by a deploy
- **THEN** that request's log line can still be retrieved from the retained
  store

#### Scenario: The proxy saw a refused request

- **WHEN** a request is refused before authentication
- **THEN** the proxy's access log line for it, with the client's address, is
  retained

### Requirement: Logs are retained in two tiers

The system SHALL keep shipped log lines searchable for 30 days and SHALL keep
them for 1 year in storage that an ordinary credential cannot alter or delete.

#### Scenario: A recent session is investigated

- **WHEN** an operator needs the lines of one session from the last 30 days
- **THEN** they can select them by `session_id` with a query, without
  downloading files

#### Scenario: An old incident is discovered

- **WHEN** an incident is discovered up to a year after it happened
- **THEN** the log lines of that period are available from the archive
- **AND** no credential used day to day could have deleted or rewritten them

#### Scenario: A lawful erasure request

- **WHEN** a data subject's erasure request covers archived log lines
- **THEN** a separately held, privileged principal can remove them, and no
  ordinary one can

### Requirement: Retained logs carry no credentials or capabilities from URLs

The system SHALL NOT retain query strings in the proxy's access log, and the
sign-in flow SHALL NOT place access or refresh tokens in any URL.

#### Scenario: A user signs in through SSO

- **WHEN** the SSO callback completes
- **THEN** the redirect URL carries no access or refresh token
- **AND** no retained log line contains either token

#### Scenario: A future route takes a secret in the query

- **WHEN** any request carries a query string
- **THEN** the retained proxy line records the path without the query

#### Scenario: The configuration is changed to log query strings

- **WHEN** the reviewed proxy or shipper configuration is edited to keep query
  strings
- **THEN** a test fails in CI

### Requirement: The shipper cannot read, delete, or re-time what it ships

The system SHALL ship logs with a credential that can only append log events
and write new archive objects, held on the host and never by the application.

#### Scenario: The VPS is compromised

- **WHEN** an attacker obtains the shipper's credential
- **THEN** they can add log lines but cannot read, delete, or shorten the
  retention of lines already shipped

### Requirement: A shipper that stops delivering pages

The system SHALL page the operator when log delivery stops, whether the shipper
has exited or is running but failing to deliver.

#### Scenario: The destination is unreachable

- **WHEN** the shipper cannot deliver to CloudWatch or S3 for longer than the
  heartbeat's grace period
- **THEN** the operator is paged through the existing paging path

### Requirement: Evidence capture does not wait on a deploy

The incident procedure SHALL require log capture before any merge to the
deployed branch during an incident, and SHALL describe capture as a query
against the retained store once it exists.

#### Scenario: A responder has a fix ready

- **WHEN** a fix is ready during an incident and the logs have not been
  captured
- **THEN** the procedure says to capture first and merge after
