## ADDED Requirements

### Requirement: Credentialed adapters MUST fail closed when credentials are missing
Adapters that require API keys, OAuth tokens, or proxies (Scopus, WoS, Scholar) SHALL return `is_active = False` when their credentials are not configured. The cascade SHALL skip them silently rather than dispatch 401/403 requests against the upstream API.

#### Scenario: Scopus adapter is loaded without an API key
- **WHEN** the cascade inspects `ScopusAdapter.is_active` and no `SCOPUS_API_KEY` environment variable is set
- **THEN** the value is `False`
- **AND** no Scopus HTTP request is dispatched for any entity in the current cascade pass

#### Scenario: WoS adapter is loaded without credentials
- **WHEN** the cascade inspects `WoSAdapter.is_active` and no WoS credentials are configured
- **THEN** the value is `False`
- **AND** no WoS HTTP request is dispatched

#### Scenario: Scholar adapter is instantiated without a proxy
- **WHEN** the `ScholarAdapter` is constructed without `use_free_proxies=True` and without a `scraper_api_key`
- **THEN** its `is_active` returns `False`
- **AND** the long-standing log warning (`ScholarAdapter running WITHOUT proxy. High risk of IP ban.`) is still emitted at construction time

### Requirement: Credentialed adapters MUST re-evaluate activation when credentials change at runtime
When credentials are rotated or added at runtime (for example via a settings reload), the next read of `is_active` SHALL reflect the new state without requiring a worker restart.

#### Scenario: Scopus API key is added after worker startup
- **WHEN** an operator sets a Scopus API key via the runtime settings reload mechanism
- **THEN** the next cascade pass observes `ScopusAdapter.is_active = True`
- **AND** subsequent enrichment requests dispatch to Scopus
