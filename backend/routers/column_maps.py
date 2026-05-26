"""
Universal column mapping for import/export operations.
Maps common column header variations → model field names.

Commerce-era aliases remain supported as a domain-specific compatibility pack,
but the core mapping table is intentionally domain-neutral.
"""

from backend.services.field_correspondence import build_legacy_column_mapping


CORE_COLUMN_MAPPING = {
    **build_legacy_column_mapping(),
    "enrichment_status": "enrichment_status",
}

COMMERCE_COLUMN_MAPPING = {
    "Product Name":      "primary_label",
    "Brand":             "secondary_label",
    "Manufacturer":      "secondary_label",
    "SKU":               "canonical_id",
    "Barcode":           "canonical_id",
    "GTIN":              "canonical_id",
}

COLUMN_MAPPING = {
    **CORE_COLUMN_MAPPING,
    **COMMERCE_COLUMN_MAPPING,
}

# model_field → clean English export header
EXPORT_COLUMN_MAPPING: dict[str, str] = {
    "primary_label":             "Primary Label",
    "secondary_label":           "Secondary Label",
    "canonical_id":              "Canonical ID",
    "entity_type":               "Entity Type",
    "domain":                    "Domain",
    "validation_status":         "Validation Status",
    "enrichment_doi":            "DOI",
    "enrichment_citation_count": "Citation Count",
    "enrichment_concepts":       "Concepts",
    "enrichment_source":         "Enrichment Source",
    "enrichment_status":         "Enrichment Status",
    "source":                    "Data Source",
}

# No typo corrections needed for universal headers
EXPORT_COLUMN_CORRECTIONS: dict[str, str] = {}
