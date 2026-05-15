## ADDED Requirements

### Requirement: Conditional TLS for gRPC channel
The Python EngineClient SHALL support TLS encryption for the gRPC channel, controlled by the `ENGINE_GRPC_TLS` environment variable.

#### Scenario: TLS enabled
- **WHEN** `ENGINE_GRPC_TLS=1`
- **THEN** the client SHALL use `grpc.aio.secure_channel` with `ssl_channel_credentials()`
- **THEN** the Bearer token SHALL be transmitted over encrypted transport

#### Scenario: TLS disabled (default)
- **WHEN** `ENGINE_GRPC_TLS` is not set or is `0`
- **THEN** the client SHALL use `grpc.aio.insecure_channel`
- **THEN** a warning SHALL be logged if the target is not localhost

### Requirement: Job ID sanitization
All job IDs constructed by the EngineClient SHALL be sanitized before use.

#### Scenario: Job ID with special characters
- **WHEN** a job ID component contains characters outside `[a-zA-Z0-9_-]`
- **THEN** those characters SHALL be stripped
- **THEN** the result SHALL be truncated to 128 characters

#### Scenario: Clean job ID
- **WHEN** a job ID contains only valid characters and is under 128 chars
- **THEN** it SHALL be used as-is

### Requirement: Auth token startup warning
The Rust engine SHALL log a warning at startup when no auth token is configured.

#### Scenario: No ENGINE_AUTH_TOKEN set
- **WHEN** the engine starts without `ENGINE_AUTH_TOKEN`
- **THEN** a `tracing::warn!` message SHALL be emitted: "No auth token configured — all gRPC requests accepted"

#### Scenario: AUTH_TOKEN set
- **WHEN** `ENGINE_AUTH_TOKEN` is set
- **THEN** the warning SHALL NOT be emitted
