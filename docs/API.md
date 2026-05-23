# Historical API Notes

This file previously documented UKIP's early commerce-oriented API surface with product, SKU, brand, and store-first examples. That material is historical context, not the active platform contract.

The current canonical API reference is [`../API.md`](../API.md). UKIP's core API now uses domain-agnostic entity terminology:

| Canonical concept | Meaning |
|---|---|
| Entity | Any ingested record normalized into the UKIP canonical model |
| Primary label | Human-readable name/title of the entity |
| Secondary label | Domain facet such as author, institution, source, classification, or a commerce brand in adapter-specific flows |
| Canonical ID | DOI, ORCID, ROR, local identifier, SKU, or other stable source identifier |
| Source adapter | Optional ingestion bridge for a specific external platform or data source |

Legacy commerce aliases remain supported for backward compatibility where existing datasets or adapter contracts require them, including `/brands`, `brand_year_matrix`, `top_brands`, `sku`, `gtin`, `barcode`, and `brand_capitalized`. New core specs, UI copy, API examples, and tests should prefer the canonical terms above.
