# sev1-paging Specification

## Purpose
A SEV1 wakes a person: ops alerts carry a severity derived from which checks are critical, Pushover pages at emergency priority through Do Not Disturb once per incident, and a Healthchecks.io dead man's switch pages when the monitor itself goes silent. Created by archiving change sev1-paging.
## Requirements
### Requirement: Pushover is an alert channel type

The system SHALL accept `pushover` as an alert channel type, store its
application token and user key encrypted, never return them, and deliver alerts
to Pushover's messages API without raising on failure.

#### Scenario: Credentials are validated and never returned

- **WHEN** an admin creates a `pushover` channel without a user key
- **THEN** the request is rejected with 422
- **AND WHEN** the channel is created with both
- **THEN** no response ever contains the token or the user key

### Requirement: Ops alerts carry a severity from the critical checks

The system SHALL classify each ops alert as `page` when `database` or
`migrations` is critical, `urgent` when `backup_freshness` or `secrets` is
critical (and no paging check is), and `info` otherwise, and SHALL map them to
Pushover priorities 2, 1 and 0.

#### Scenario: The database going down pages

- **WHEN** the database check becomes critical
- **THEN** a Pushover channel receives a priority-2 message with `retry` and
  `expire` set

#### Scenario: A stale backup does not wake anyone

- **WHEN** only `backup_freshness` is critical
- **THEN** the Pushover message has priority 1

#### Scenario: Slack sees the same classification

- **WHEN** an alert is `page`
- **THEN** its Slack message starts with `[PAGE]`

### Requirement: A page is sent once per incident

The system SHALL send severity `page` only when the set of critical paging
checks grows relative to the previous observation, and SHALL send reminders and
unrelated changes during that incident as `info`.

#### Scenario: A reminder during an outage does not page again

- **WHEN** the database has been critical for longer than the reminder interval
- **THEN** the reminder is sent at priority 0

#### Scenario: A second paging check failing pages again

- **WHEN** migrations become critical while the database already was
- **THEN** a new priority-2 page is sent

### Requirement: The monitor reports that it is alive

The system SHALL, when `UKIP_OPS_HEARTBEAT_URL` is set, ping it after every
monitor cycle, ping `<url>/fail` when the evaluation raised, never raise, and
never log the URL.

#### Scenario: A failed evaluation reports failure

- **WHEN** the checks raise during a cycle
- **THEN** the heartbeat request goes to the `/fail` path

#### Scenario: An unreachable heartbeat service does not break the cycle

- **WHEN** the heartbeat request times out
- **THEN** the cycle completes and the next one runs

### Requirement: The paging path is testable end to end

The system SHALL, for a Pushover channel's test action, send a real
emergency-priority message that expires on its own within a minute.

#### Scenario: Testing a Pushover channel

- **WHEN** an admin tests a Pushover channel
- **THEN** a priority-2 message with `expire` of 60 seconds is sent
