## 1. Audit and governance

- [x] 1.1 Inventory commerce residues across frontend, backend, engine, specs, docs, and tests.
- [x] 1.2 Classify residues as core debt, adapter-specific, legacy-compatible, or historical documentation.
- [x] 1.3 Link cleanup to `canonical-semantic-data-governance` and `ukip-enterprise-architecture-governance`.
- [x] 1.4 Add regression guidance so future generic UI copy avoids commerce-first examples.

## 2. Core UI copy cleanup

- [x] 2.1 Update import wizard labels: secondary label, canonical ID, recommended mapping copy, stable identifier hint.
- [x] 2.2 Update entity detail labels for secondary label and canonical ID.
- [x] 2.3 Update harmonization stat key/copy from total products to total entities while preserving `total_products` fallback.
- [x] 2.4 Update import/export danger zone copy and export filename away from product terminology.
- [x] 2.5 Update EN/ES translations for active generic workflows.
- [x] 2.6 Run focused frontend lint/type checks.

## 3. Mapping and prompt cleanup

- [x] 3.1 Update backend field descriptions in `backend/routers/ingest.py` to domain-neutral/scientific examples.
- [x] 3.2 Split `COLUMN_MAPPING` into core aliases and commerce adapter aliases.
- [x] 3.3 Preserve commerce aliases through adapter/domain-pack mapping when commerce sources are active.
- [x] 3.4 Update LLM mapping tests to avoid commerce-first fixtures in core tests.
- [x] 3.5 Add tests for DOI, ORCID, ROR, title, author, institution, and local identifier mapping.

## 4. Analytics and report terminology

- [x] 4.1 Rename dashboard/report presentation from `top_brands` to neutral facet language while maintaining API compatibility.
- [x] 4.2 Update report builder copy from Top Brands / Classifications to domain-relevant secondary labels or facets.
- [x] 4.3 Update analytics dashboard heatmap labels from Brand x Year to neutral/domain-aware terms.
- [x] 4.4 Update PPT/Excel export labels to avoid brand/product assumptions.

## 5. Adapter containment

- [x] 5.1 Reframe store integrations as optional commerce source adapters.
- [x] 5.2 Add feature flag or deployment visibility policy for commerce integrations.
- [x] 5.3 Ensure scheduled imports from stores pass through source profiling and canonical mapping.
- [x] 5.4 Keep adapter tests commerce-specific and clearly scoped.

## 6. Engine and backend compatibility

- [x] 6.1 Move commerce fields in analytics allowlists/defaults into explicit legacy/domain-specific compatibility groups.
- [x] 6.2 Ensure scientific domains default to author, institution, concept, source, year, DOI, and authority fields.
- [x] 6.3 Preserve reading of existing `sku`, `gtin`, `barcode`, and `brand_capitalized` attributes without foregrounding them.
- [x] 6.4 Add regression tests for scientific default analytics fields.

## 7. Documentation refresh

- [x] 7.1 Update `API.md` active examples away from RawProduct/product-first language.
- [x] 7.2 Update `frontend/README.md` from Product Catalog to UKIP entity/dataset workspace.
- [x] 7.3 Mark historical commerce evolution docs as historical context where appropriate.
- [x] 7.4 Update OpenSpec config example comment away from e-commerce.

## 8. Validation

- [x] 8.1 Run `npx openspec validate domain-agnostic-core-cleanup --strict`.
- [x] 8.2 Run focused backend tests for ingest mapping, import/export, analytics, and adapters.
- [x] 8.3 Run focused frontend tests for import, entity detail, harmonization, import/export, and dashboard copy.
- [x] 8.4 Run full lint/type checks for modified frontend surfaces.
