## ADDED Requirements

### Requirement: Concrete enrichment adapters MUST declare activation state explicitly
Every concrete subclass of `BaseScientometricAdapter` SHALL declare an `is_active` attribute (typically a property) that returns a `bool`. The enrichment cascade reads activation via `getattr(adapter, 'is_active', False)`; a missing attribute is treated as inactive and silently skips the provider. The contract makes the omission impossible to merge.

#### Scenario: A new adapter ships without is_active
- **WHEN** a developer adds a new `BaseScientometricAdapter` subclass without an `is_active` property
- **THEN** the auto-discovery contract test fails at CI time
- **AND** the merge is blocked until the adapter declares the attribute

#### Scenario: OpenAlex adapter is read by the cascade
- **WHEN** the enrichment worker iterates the cascade and inspects `OpenAlexAdapter.is_active`
- **THEN** the value is `True` because OpenAlex does not require an API key (polite-pool via mailto)
- **AND** OpenAlex participates in the cascade alongside Crossref, PubMed, Semantic Scholar, and DBLP

#### Scenario: Scholar adapter without proxy
- **WHEN** the `ScholarAdapter` is instantiated without a configured proxy
- **THEN** its `is_active` returns `False`
- **AND** the cascade skips Scholar without raising, matching the long-standing log warning

### Requirement: Adapter activation MUST fail closed on missing credentials
Adapters that require credentials (Scopus, WoS) SHALL return `is_active = False` when their credentials are not configured. The cascade SHALL skip them silently rather than emit 401/403 requests against the upstream API.

#### Scenario: Scopus adapter without API key
- **WHEN** the cascade inspects `ScopusAdapter.is_active` and no API key is configured
- **THEN** the value is `False`
- **AND** no Scopus HTTP request is dispatched for this entity
