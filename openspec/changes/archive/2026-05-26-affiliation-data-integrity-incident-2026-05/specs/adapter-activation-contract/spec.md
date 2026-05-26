## ADDED Requirements

### Requirement: Concrete enrichment adapters MUST declare `is_active`
Every concrete subclass of `BaseScientometricAdapter` SHALL expose an `is_active` attribute (a property, a class attribute, or an instance attribute) that returns a Python `bool`. The enrichment cascade reads activation via `getattr(adapter, 'is_active', False)`. A missing attribute is treated as inactive and silently skips the provider — therefore the omission must be impossible to merge.

#### Scenario: A new adapter ships without `is_active`
- **WHEN** a developer adds a new `BaseScientometricAdapter` subclass without an `is_active` attribute
- **THEN** the auto-discovery contract test in `backend/tests/test_enrichment_adapter_contract.py` fails at CI time
- **AND** the merge is blocked until the adapter declares the attribute

#### Scenario: An adapter declares `is_active` returning a non-bool
- **WHEN** an adapter declares `is_active` returning a truthy value that is not a `bool` (for example `int` or `str`)
- **THEN** the contract test fails with a message naming the offending adapter and the actual type returned

#### Scenario: OpenAlex adapter is read by the cascade
- **WHEN** the enrichment worker inspects `OpenAlexAdapter.is_active`
- **THEN** the value is `True` — OpenAlex does not require an API key (polite-pool via mailto)
- **AND** OpenAlex appears as an active provider in the cascade ordering

### Requirement: Adapter activation MUST be inspectable without performing a network call
Reading `adapter.is_active` SHALL NOT trigger an HTTP request, a database query, or any other I/O. The cascade evaluates activation for every entity it processes; an I/O-bound check would add hundreds of round-trips per minute under load.

#### Scenario: Cascade reads `is_active` 500 times in a tight loop
- **WHEN** the enrichment worker iterates the cascade once per entity across 500 pending entities
- **THEN** the cumulative time spent reading `is_active` across all adapters is under 50 ms
- **AND** no outbound HTTP request is observed
