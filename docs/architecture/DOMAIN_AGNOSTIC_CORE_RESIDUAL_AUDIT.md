# Domain-Agnostic Core Residual Audit

## Purpose

This audit identifies residual assumptions from UKIP's foundational e-commerce/catalog phase that still appear in core product surfaces, API documentation, tests, analytics defaults, and dataset mapping language.

The goal is not to remove e-commerce as a future enrichment domain. The goal is to keep commerce-specific assumptions out of the core canonical model and delegate them to source adapters, domain packs, tailor-made enrichment, and optional connectors.

## Review Scope

Reviewed areas:

- Backend routers and service contracts
- Frontend dataset import, entity detail, harmonization, import/export, integrations, dashboards, and translations
- Engine analytics allowlists and skip-field defaults
- OpenSpec and product documentation
- Tests that encode legacy field examples

Search terms included e-commerce, commerce, shop, store, product, SKU, price, inventory, customer, order, cart, checkout, sales, vendor, merchant, brand, GTIN, barcode, product_name, brand_capitalized, total_products, and related Spanish terms.

## Executive Finding

UKIP is mostly architecturally ready for a domain-agnostic semantic core, but several user-facing and developer-facing surfaces still leak the old e-commerce mental model. The highest-risk residues are not the explicit commerce adapters themselves; those can remain as domain adapters. The higher risk is generic UI, mapping, analytics, reports, and documentation that still describe all records as products, brands, SKUs, stores, or commerce catalogs.

## Residual Classes

### 1. Legitimate domain-specific adapters

These should not be deleted outright. They should be treated as optional commerce source adapters and kept outside the core scientific intelligence narrative.

- `backend/adapters/shopify.py`
- `backend/adapters/woocommerce.py`
- `backend/adapters/bsale.py`
- `backend/adapters/custom.py`
- `backend/routers/stores.py`
- `frontend/app/integrations/page.tsx`
- `frontend/app/integrations/[id]/page.tsx`

Recommended action:

- Reclassify as `commerce-source-adapters`.
- Hide or feature-flag commerce store integrations in scientific/research deployments.
- Ensure store connectors write into the same source profiling and canonical mapping path used by all other source adapters.

### 2. Core UI copy that still says product/SKU/brand

These are true residues because they appear in generic dataset workflows.

Examples:

- `frontend/app/import/importWizardParts.tsx`
  - `Secondary Label (brand / author)`
  - `Canonical ID (SKU / DOI / barcode)`
  - recommended mapping copy mentions DOI, SKU, barcode together as core examples
- `frontend/app/entities/[id]/page.tsx`
  - `Etiqueta secundaria (marca / autor)`
  - `ID canónico (SKU / código)`
- `frontend/app/harmonization/page.tsx`
  - UI still uses translation key `page.harmonization.stat_total_products`
  - interface still accepts `total_products` as legacy fallback
- `frontend/app/import-export/page.tsx`
  - `Delete all product records`
  - `Remove all products from the database`
  - export filename defaults to `products_export.xlsx`
- `frontend/app/i18n/translations.ts`
  - multiple active translations still mention products, SKU, barcode, brands, mapped products, and e-commerce stores

Recommended action:

- Replace core copy with neutral semantic language:
  - `product records` -> `records` or `entities`
  - `SKU / DOI / barcode` -> `DOI / ORCID / ROR / local identifier`
  - `brand / author` -> `author / institution / source label`
  - `Total Products` -> `Total Entities`
- Keep commerce examples only in adapter-specific help text.

### 3. Backend mapping and LLM prompt assumptions

These leak e-commerce into source mapping suggestions.

Examples:

- `backend/routers/ingest.py`
  - `primary_label`: `product name, paper title, person name`
  - `secondary_label`: `brand, author, publisher, organization`
  - `canonical_id`: `SKU, DOI, ISBN, GTIN, barcode, record ID`
  - `entity_type`: `product, paper, person, organization`
- `backend/routers/column_maps.py`
  - maps `Product Name`, `Brand`, `SKU`, `Barcode`, `GTIN` directly in the universal mapping table

Recommended action:

- Split universal mapping aliases from domain-pack aliases.
- Keep `DOI`, `ORCID`, `ROR`, `ISBN`, `ISSN`, `local_id`, and `record_id` in core.
- Move `SKU`, `GTIN`, `Barcode`, `Product Name`, `Brand`, `Manufacturer` to a commerce adapter mapping pack.
- Update the LLM mapping prompt to describe UKIP as domain-agnostic and science-ready without foregrounding product examples.

### 4. Analytics, reports, and dashboards still use brand/product concepts

These are medium-to-high impact because they shape stakeholder interpretation.

Examples:

- `backend/main.py`
  - default report sections include `top_brands`
  - OpenAPI text references store integrations for admin
- `backend/routers/dashboards.py`
  - widget type and label: `top_brands`, `Top Brands / Values`
- `backend/report_builder.py`
  - `_section_top_brands`
  - `Top Brands / Classifications`
- `backend/exporters/pptx_exporter.py`
  - Slide 4: `Top Brands`
- `frontend/app/dashboards/widgets.tsx`
  - `TopBrandsWidget`
  - fetches `/brands`
- `frontend/app/analytics/dashboard/page.tsx`
  - `brand_year_matrix`
  - comments and labels still frame a heatmap as Brand x Year
- `frontend/app/analytics/AnalyticsEnrichmentSection.tsx`
  - copy says `raw product records`

Recommended action:

- Rename presentation layer to `top_secondary_labels`, `top_entity_facets`, or `top_institutions_authors_sources` depending on context.
- Maintain backward-compatible endpoint aliases temporarily.
- Replace dashboard narrative with research/stakeholder language.

### 5. Engine and analyzer field defaults

These are lower immediate UX risk but matter for architecture cleanliness.

Examples:

- `engine/src/pipelines/analytics/mod.rs`
  - allowlist includes `brand_capitalized`, `sku`, `gtin`, `barcode`
  - default correlation fields include `brand_capitalized`
- `engine/src/pipelines/analytics/correlation.rs`
  - skip fields include `sku`, `gtin`, `barcode`
- `backend/analyzers/correlation.py`
  - skip fields include `gtin_*`, `brand_lower`, `model`, `unit_of_measure`, `entity_key`

Recommended action:

- Keep broad support for legacy fields when reading existing data.
- Move commerce fields into a legacy/domain adapter compatibility list.
- Ensure default analytics for scientific domains prefer author, institution, source, year, concepts, entity type, DOI, and authority fields.

### 6. Documentation and historical architecture

Some docs are useful historical evidence; others are misleading if treated as current product truth.

Examples:

- `docs/EVOLUTION_STRATEGY.md` correctly documents the evolution away from e-commerce.
- `docs/API.md` still contains older product-centric contracts and examples.
- `frontend/README.md` still says `Product Catalog`.
- `docs/SCIENTOMETRICS.md` references `ProductTable.tsx`.
- OpenSpec `openspec/config.yaml` still has example comment `Domain: e-commerce platform`.

Recommended action:

- Keep historical docs only when they are explicitly framed as evolution/history.
- Update active docs and README surfaces to domain-agnostic/scientific intelligence language.
- Archive or mark stale API examples that reference `RawProduct`, product records, brands, and SKU as core concepts.

## Priority Cleanup Plan

### P0: User-facing core neutrality

- Update import wizard labels and helper copy.
- Update entity detail labels.
- Update import/export danger zone copy and export filename.
- Update harmonization stats copy from products to entities.
- Update active translations in English and Spanish.

### P1: Mapping governance

- Introduce core vs domain-pack mapping aliases.
- Move commerce aliases out of universal mapping tables.
- Update AI mapping prompt to avoid e-commerce-first language.
- Add tests proving scientific fields map cleanly without SKU/brand examples.

### P2: Analytics/report naming

- Rename `top_brands` presentation to neutral facet/secondary-label language.
- Keep backward-compatible API aliases while transitioning reports and dashboards.
- Update dashboard heatmap labels away from Brand x Year where the domain is scientific.

### P3: Adapter containment

- Add feature flag or deployment policy for commerce store integrations.
- Reframe `/integrations` copy so stores are optional source adapters, not the default product path.
- Document commerce enrichment as a future domain pack rather than core model behavior.

### P4: Legacy tests and docs

- Update tests that use brand/SKU only as generic examples.
- Keep adapter tests commerce-specific.
- Refresh `API.md`, `frontend/README.md`, and stale docs.

## Recommended Spec

Create and implement `domain-agnostic-core-cleanup` as a governance and cleanup change subordinate to:

- `canonical-semantic-data-governance`
- `entity-provenance-layering`
- `ukip-enterprise-architecture-governance`
- `authority-enrichment-bridge`

The spec should prevent future regressions by requiring any domain-specific terminology to live in adapters, domain packs, or explicitly scoped UI.
