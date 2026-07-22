## ADDED Requirements

### Requirement: API key scopes are authorization-bearing

The system SHALL reject a request authenticated with a UKIP API key when the
scope required by the requested operation is not satisfied by the scopes granted
to that key.

#### Scenario: Read key is denied a mutating request

- **WHEN** a request presents an API key granted `["read"]` to a `POST`,
  `PUT`, `PATCH`, or `DELETE` endpoint
- **AND** scope enforcement is enabled
- **THEN** the response status is `403`
- **AND** the response body names the scope that was required

#### Scenario: Write key is allowed a mutating request

- **WHEN** a request presents an API key granted `["write"]` to a `POST` endpoint
  that is not under an admin-classified path
- **THEN** the request proceeds to the endpoint

#### Scenario: JWT sessions are unaffected

- **WHEN** a request presents a JWT bearer token rather than an API key
- **THEN** no scope check is applied and behaviour is identical to before this
  change

### Requirement: Required scope is derived from method and route

The system SHALL determine the required scope for every route without
per-endpoint annotation, using an ordered rule set: admin-path table first, then
an explicit read-override registry, then HTTP method, defaulting to `write`.

#### Scenario: Safe methods require read

- **WHEN** the request method is `GET`, `HEAD`, or `OPTIONS`
- **AND** the route is not in the admin-path table
- **THEN** the required scope is `read`

#### Scenario: Unsafe methods require write

- **WHEN** the request method is `POST`, `PUT`, `PATCH`, or `DELETE`
- **AND** the route is neither in the admin-path table nor the read-override
  registry
- **THEN** the required scope is `write`

#### Scenario: Admin paths require admin on every method

- **WHEN** the route is in the admin-path table
- **THEN** the required scope is `admin` regardless of HTTP method
- **AND** a `GET` against that route with a `read`-only key is denied

#### Scenario: Read-only POST endpoints are overridden

- **WHEN** a `POST` route is registered in the read-override registry because it
  performs a query rather than a mutation
- **THEN** the required scope is `read`

#### Scenario: Route matching uses the templated path

- **WHEN** a request targets a parameterized route and the concrete URL contains
  a path segment that resembles an admin-table entry
- **THEN** classification uses the route template, not the concrete URL

### Requirement: Scopes form an escalating hierarchy

The system SHALL treat `admin` as implying `write`, and `write` as implying
`read`, when testing whether granted scopes satisfy a requirement.

#### Scenario: Admin scope satisfies a read requirement

- **WHEN** a key granted `["admin"]` calls a `read`-classified endpoint
- **THEN** the request proceeds

#### Scenario: Write scope does not satisfy an admin requirement

- **WHEN** a key granted `["write"]` calls an endpoint in the admin-path table
- **THEN** the request is denied

### Requirement: Scope restricts but never elevates privilege

The system SHALL apply the scope check in addition to, and never in place of,
the role-based access control of the key's owning user.

#### Scenario: Admin scope on a low-privilege user does not grant admin access

- **WHEN** a key granted `["admin"]` is owned by a user with the `viewer` role
- **AND** the request targets an endpoint requiring an `admin` role
- **THEN** the request is denied by role-based access control

#### Scenario: Read scope on a privileged user is still restricted

- **WHEN** a key granted `["read"]` is owned by a `super_admin`
- **AND** the request targets a `write`-classified endpoint
- **THEN** the request is denied by the scope check

### Requirement: Every route resolves to a scope

The system SHALL classify every registered route, so that a route added without
explicit configuration receives the fail-closed default rather than no
requirement.

#### Scenario: Route coverage is asserted

- **WHEN** the route-coverage test enumerates the application's routes
- **THEN** every route resolves to exactly one of `read`, `write`, or `admin`
- **AND** the test fails if any route resolves to no scope

### Requirement: Enforcement is gated by a rollout flag with a warn mode

The system SHALL support a warn mode in which scope violations are recorded but
not blocked, controlled by `UKIP_API_KEY_SCOPES_ENFORCED`, defaulting to warn.

#### Scenario: Warn mode records without blocking

- **WHEN** enforcement is disabled
- **AND** a key granted `["read"]` calls a `write`-classified endpoint
- **THEN** the request proceeds normally
- **AND** an audit entry with action `api_key.scope_violation` is written
  recording the key prefix, HTTP method, route, required scope, and granted
  scopes

#### Scenario: Violation records never contain the credential

- **WHEN** a scope violation is recorded in warn or enforce mode
- **THEN** the record contains the key prefix only
- **AND** the record contains neither the full API key nor its hash

#### Scenario: Effective enforcement state is observable

- **WHEN** `GET /health` is requested
- **THEN** the `features` section reports whether API key scope enforcement is
  active

### Requirement: Scope enforcement covers every API key entry point

The system SHALL apply the scope check on all paths that accept a UKIP API key,
including optional authentication and the WebSocket handshake.

#### Scenario: Optional-auth endpoints enforce scope

- **WHEN** a `write`-classified endpoint that uses optional authentication
  receives a `read`-only key
- **AND** enforcement is enabled
- **THEN** the request is denied rather than downgraded to anonymous access

#### Scenario: WebSocket handshake requires read scope

- **WHEN** a WebSocket connection presents an API key
- **THEN** the connection is accepted only if the key satisfies `read`
