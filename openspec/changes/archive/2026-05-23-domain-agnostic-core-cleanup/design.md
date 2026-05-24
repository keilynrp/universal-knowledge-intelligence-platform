## Context

UKIP's current architecture already uses `RawEntity`, domain scoping, canonical identity, enrichment, authority, provenance, graph materialization, and scientific connectors. However, older names and examples remain from the foundational commerce phase. The cleanup must be careful: some residues are true product debt, while others are legitimate adapter-specific capabilities.

## Goals / Non-Goals

**Goals:**

- Remove commerce-first terminology from generic user journeys.
- Separate universal mapping aliases from commerce adapter aliases.
- Preserve commerce support as an optional domain pack.
- Keep backward compatibility for existing data where fields such as `sku`, `gtin`, or `brand_capitalized` exist.
- Update tests and docs so the current product thesis is clear.

**Non-Goals:**

- Delete Shopify, WooCommerce, Bsale, or custom adapters immediately.
- Break existing datasets that include SKU/GTIN/product fields.
- Pretend commerce enrichment will never be supported.
- Rename every internal historical function in one risky migration.

## Classification

### Core-neutral

Allowed in generic surfaces:

- entity, record, source, dataset, corpus, domain, canonical identifier
- primary label, secondary label, authority identifier, local identifier
- author, institution, publication, DOI, ORCID, ROR, concept, place when the active domain is scientific/research

### Adapter-specific

Allowed only in commerce adapter surfaces, adapter docs, or domain packs:

- product, SKU, GTIN, barcode, brand, store, cart, checkout, inventory, price, merchant, customer, order

### Legacy-compatible

Allowed in code only when reading existing data or maintaining backward-compatible endpoints:

- `brand_capitalized`
- `sku`
- `gtin`
- `barcode`
- `total_products`
- `products_deleted`
- `top_brands`

## Decisions

### D1: Generic UI must not teach commerce as the default model

**Decision:** Generic import, entity detail, harmonization, import/export, dashboard, and report surfaces SHALL use domain-neutral labels.

**Rationale:** The core UKIP experience should read as a semantic intelligence platform, not a product catalog manager.

### D2: Commerce identifiers belong in domain packs

**Decision:** SKU, GTIN, barcode, product name, brand, manufacturer, and store-specific fields SHALL be mapped through commerce adapters or domain packs rather than universal mapping defaults.

**Rationale:** They are valid identifiers, but not universal identity examples.

### D3: Backward compatibility remains explicit

**Decision:** Legacy commerce fields MAY remain in compatibility paths, but they SHALL be labeled as legacy/domain-specific where possible.

**Rationale:** Existing datasets and tests should not break during cleanup.

### D4: Documentation distinguishes history from current architecture

**Decision:** Historical commerce references MAY remain in evolution documents, but active docs SHALL describe UKIP's current domain-agnostic semantic architecture.

**Rationale:** History is useful; stale product claims are confusing.

## Rollout Plan

1. Update user-facing copy and translations in core workflows.
2. Update import/export filenames, labels, and confirmation text.
3. Update generic backend mapping descriptions and AI prompt copy.
4. Split universal column aliases from commerce adapter aliases.
5. Rename dashboard/report labels from brand/product terminology to neutral facet terminology.
6. Feature-flag or visually reframe commerce integrations as optional source adapters.
7. Update core tests to use neutral/scientific examples and keep commerce examples in adapter tests.
8. Refresh active documentation and archive stale API/product docs where appropriate.
