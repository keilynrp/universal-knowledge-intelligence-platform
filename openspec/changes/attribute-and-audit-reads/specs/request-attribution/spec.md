## ADDED Requirements

### Requirement: The acting principal is resolved once, by authentication

The system SHALL record the principal of every request that authentication
accepts, meaning the user id plus the session id (JWT) or the API key id (API
key), at the point where the auth dependency accepts the credential. It SHALL
record nothing for a request that authentication refuses.

#### Scenario: JWT request records user and session

- **WHEN** a request presents a JWT whose session is live
- **THEN** the recorded principal has that user's id and the token's session id
- **AND** no API key id

#### Scenario: API key request records user and key

- **WHEN** a request presents a valid `ukip_` API key
- **THEN** the recorded principal has the owning user's id and the key's id
- **AND** no session id

#### Scenario: Refused credential records nothing

- **WHEN** a request presents a token whose session was revoked, an expired
  token, or an unknown API key
- **THEN** no principal is recorded for that request

### Requirement: The request log attributes authenticated requests

The system SHALL include the principal's `user_id`, and `session_id` or
`api_key_id`, in the `request_completed` and `request_failed` log records of
every request with a recorded principal. It SHALL omit these fields entirely,
rather than emit a placeholder, when there is no principal.

#### Scenario: Authenticated read is attributable from the log alone

- **WHEN** an authenticated `GET /entities` completes
- **THEN** its `request_completed` record contains `user_id` and `session_id`

#### Scenario: Anonymous request carries no identity fields

- **WHEN** an unauthenticated request to a public endpoint completes
- **THEN** its log record contains no `user_id`, `session_id` or `api_key_id`
  field

#### Scenario: Credentials never reach the log

- **WHEN** any request is logged
- **THEN** the record contains no bearer token, API key, header value, request
  body or query value

### Requirement: Audit rows carry the resolved principal

The system SHALL populate `user_id`, `session_id` and `api_key_id` on every
audit row written by the audit middleware from the recorded principal, and
SHALL NOT derive identity by decoding the presented token.

#### Scenario: API key mutation is attributed

- **WHEN** a `POST` is made with an API key and succeeds
- **THEN** its audit row has the key owner's `user_id` and the key's
  `api_key_id`

#### Scenario: A revoked token lends no identity

- **WHEN** a `PUT` presents a token whose session was revoked and is refused
  with `401`
- **THEN** its audit row, if one is written, has no `user_id`, `username` or
  `session_id`

#### Scenario: Deleting a key does not touch its evidence

- **WHEN** an API key named by audit rows is deleted
- **THEN** those rows remain with their `api_key_id` unchanged
