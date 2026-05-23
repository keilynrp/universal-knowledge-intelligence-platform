## ADDED Requirements

### Requirement: Generic core surfaces use domain-neutral semantics
UKIP SHALL use domain-neutral terminology in generic core surfaces unless the active domain or source adapter explicitly requires domain-specific language.

#### Scenario: User imports a scientific dataset
- **WHEN** the import wizard displays generic mapping fields
- **THEN** labels refer to primary label, secondary label, canonical identifier, entity type, source, and domain
- **AND** commerce examples such as product, SKU, barcode, brand, or store are not foregrounded

#### Scenario: Entity detail shows canonical identity
- **WHEN** entity detail renders core fields
- **THEN** canonical identity is described as a stable or canonical identifier
- **AND** source-specific identifiers are shown as source evidence or domain-specific attributes

### Requirement: Legacy fields remain compatible but not canonical defaults
UKIP SHALL preserve compatibility with existing commerce-era fields without treating them as canonical defaults.

#### Scenario: Existing record has SKU
- **WHEN** an existing record includes a SKU in source attributes
- **THEN** UKIP can display it as source or adapter-specific evidence
- **AND** does not describe SKU as the default canonical identifier type for all domains
