## ADDED Requirements

### Requirement: Commerce capabilities are scoped as adapters
UKIP SHALL scope Shopify, WooCommerce, Bsale, custom store, SKU, GTIN, barcode, inventory, price, order, and store concepts to commerce adapters or domain packs.

#### Scenario: Commerce source adapter is enabled
- **WHEN** a tenant enables a commerce source adapter
- **THEN** UKIP may show commerce-specific labels, mappings, and help text inside that adapter workflow
- **AND** imported records still flow through source profiling, mapping suggestions, canonical modeling, authority, and enrichment governance

#### Scenario: Scientific deployment has commerce adapters disabled
- **WHEN** commerce adapters are disabled by deployment policy or feature flag
- **THEN** generic navigation and onboarding do not present store or product catalog workflows as core modules

### Requirement: Commerce aliases are not universal mappings
Commerce-specific column aliases SHALL NOT be part of universal mapping defaults unless they are marked as domain-specific compatibility aliases.

#### Scenario: File has SKU column
- **WHEN** a generic file includes a SKU column
- **THEN** UKIP may preserve it as a source attribute or commerce-domain candidate
- **AND** only maps it to canonical identity when mapping rules, adapter context, or user review supports that decision
