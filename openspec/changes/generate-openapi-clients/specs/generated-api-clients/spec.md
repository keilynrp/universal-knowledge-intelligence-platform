## ADDED Requirements

### Requirement: Operation identifiers are a stable public interface

The system SHALL derive OpenAPI operation identifiers from route name and tag
rather than from implementation function names, so that generated client method
names do not change when internal code is refactored.

#### Scenario: Operation IDs are deterministic

- **WHEN** the OpenAPI document is generated twice from an unchanged application
- **THEN** the operation identifiers are identical

#### Scenario: Operation IDs survive an internal rename

- **WHEN** a route handler function is renamed without changing its path, method,
  tag, or route name
- **THEN** the operation identifier is unchanged

#### Scenario: Operation IDs are pinned by test

- **WHEN** the operation identifier of a representative endpoint changes
- **THEN** a test fails, requiring the change to be acknowledged deliberately

### Requirement: Clients are generated from the published specification

The system SHALL provide TypeScript and Python clients generated from the
application's OpenAPI document by a single reproducible command.

#### Scenario: One command regenerates everything

- **WHEN** the SDK generation script is run
- **THEN** the OpenAPI document, the TypeScript client, and the Python client are
  all regenerated

#### Scenario: Generation requires no running server

- **WHEN** the OpenAPI document is produced
- **THEN** it is obtained from the application object directly, without binding a
  port, connecting to a database, or running startup

#### Scenario: Generation is reproducible

- **WHEN** the generation script is run twice with no source change
- **THEN** the second run produces no diff

### Requirement: Client drift fails continuous integration

The system SHALL fail CI when the committed clients do not match the clients
that regeneration would produce.

#### Scenario: Route change without regeneration is rejected

- **WHEN** a change modifies a route's path, method, or schema
- **AND** the generated clients are not regenerated in the same change
- **THEN** the drift check fails and reports the difference

#### Scenario: Generator versions are pinned

- **WHEN** the generation toolchain is declared
- **THEN** generator versions are pinned, so an upstream generator release cannot
  produce a diff on an unrelated change

### Requirement: Clients accept both credential kinds

The system SHALL provide clients that authenticate with either a JWT bearer
token or a UKIP API key through a single credential input.

#### Scenario: API key is accepted

- **WHEN** a client is constructed with a `ukip_` API key
- **THEN** requests carry it as a bearer credential and are authenticated

#### Scenario: JWT is accepted

- **WHEN** a client is constructed with a JWT obtained from the token endpoint
- **THEN** requests are authenticated

### Requirement: Clients document the scope model

The system SHALL document, in each client's README, the API key scope model and
the meaning of a scope denial.

#### Scenario: Scope denial is explained

- **WHEN** an integrator reads a client README
- **THEN** it states which scope each class of operation requires, that scopes
  escalate, and that a scope-related `403` indicates a credential that is too
  narrow rather than a user lacking permission

#### Scenario: Stability of the surface is stated honestly

- **WHEN** an integrator reads the SDK README
- **THEN** it states that the client is generated from the full API surface and
  identifies which parts carry a stability commitment

### Requirement: Clients are smoke tested against the real application

The system SHALL verify each generated client against the running application
object, covering authentication, a read call, and a scope denial.

#### Scenario: Authenticated read succeeds

- **WHEN** a smoke test authenticates and lists entities through a generated
  client
- **THEN** it receives a typed result

#### Scenario: Scope denial is distinguishable

- **WHEN** a smoke test calls a write operation using a read-scoped key with
  enforcement enabled
- **THEN** the client surfaces a `403` that is distinguishable from a transport
  failure or an authentication failure
