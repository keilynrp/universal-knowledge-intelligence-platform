## ADDED Requirements

### Requirement: SIGTERM graceful shutdown
The Rust engine SHALL handle SIGTERM for graceful shutdown in containerized environments.

#### Scenario: SIGTERM received (Unix)
- **WHEN** the engine receives SIGTERM
- **THEN** it SHALL initiate the same graceful shutdown as Ctrl-C
- **THEN** in-flight requests SHALL complete within the shutdown timeout
- **THEN** the gRPC server SHALL stop accepting new connections

#### Scenario: Windows environment
- **WHEN** running on Windows
- **THEN** only Ctrl-C (SIGINT) handling SHALL be active
- **THEN** the build SHALL NOT fail due to missing Unix signal support

### Requirement: DB pool timeout configuration
The database connection pool SHALL have bounded timeouts to prevent indefinite blocking.

#### Scenario: Database unreachable
- **WHEN** the database is unreachable
- **THEN** connection acquisition SHALL fail after 5 seconds (not block indefinitely)
- **THEN** the error SHALL propagate as `PipelineError::Database`

#### Scenario: Idle connections
- **WHEN** a connection has been idle for 600 seconds
- **THEN** it SHALL be closed and returned to the pool

#### Scenario: Connection lifetime
- **WHEN** a connection has been alive for 1800 seconds
- **THEN** it SHALL be recycled regardless of idle status

### Requirement: Atomic concurrent job limiting
The `can_accept` / `create` flow SHALL use an atomic mechanism to prevent exceeding `max_concurrent_jobs`.

#### Scenario: Concurrent requests at capacity
- **WHEN** two requests arrive simultaneously when `current_jobs == max_jobs - 1`
- **THEN** exactly one SHALL be accepted
- **THEN** the other SHALL receive `Status::resource_exhausted`

### Requirement: Optimized release profile
The Cargo.toml SHALL include a `[profile.release]` section optimized for production.

#### Scenario: Release build
- **WHEN** `cargo build --release` is executed
- **THEN** LTO, single codegen unit, and symbol stripping SHALL be applied
