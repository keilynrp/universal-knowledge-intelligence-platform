"""
Universal column mapping for import/export operations.
Maps common column header variations → model field names.

Commerce-era aliases remain supported as a domain-specific compatibility pack,
but the core mapping table is intentionally domain-neutral.
"""

CORE_COLUMN_MAPPING = {
    # primary_label synonyms
    "Name":              "primary_label",
    "Title":             "primary_label",
    "Label":             "primary_label",
    "name":              "primary_label",
    "title":             "primary_label",
    "label":             "primary_label",
    "primary_label":     "primary_label",

    # secondary_label synonyms
    "Author":            "secondary_label",
    "Authors":           "secondary_label",
    "Institution":       "secondary_label",
    "Organization":      "secondary_label",
    "Publisher":         "secondary_label",
    "Venue":             "secondary_label",
    "Source":            "secondary_label",
    "secondary_label":   "secondary_label",

    # canonical_id synonyms
    "ID":                "canonical_id",
    "Id":                "canonical_id",
    "UID":               "canonical_id",
    "DOI":               "canonical_id",
    "doi":               "canonical_id",
    "DOI Number":        "canonical_id",
    "Código":            "canonical_id",
    "Codigo":            "canonical_id",
    "Code":              "canonical_id",
    "Identifier":        "canonical_id",
    "Identificador":     "canonical_id",
    "Identificador único":  "canonical_id",
    "Identificador unico":  "canonical_id",
    "ID único":          "canonical_id",
    "ID unico":          "canonical_id",
    "Tipo de Identificador": "canonical_id",
    "ORCID":             "canonical_id",
    "ORCID ID":          "canonical_id",
    "ROR":               "canonical_id",
    "ROR ID":            "canonical_id",
    "ISBN":              "canonical_id",
    "ISSN":              "canonical_id",
    "PMID":              "canonical_id",
    "PubMed ID":         "canonical_id",
    "PubMed":            "canonical_id",
    "WOS ID":            "canonical_id",
    "WoS ID":            "canonical_id",
    "UT (Unique WOS ID)": "canonical_id",
    "Scopus ID":         "canonical_id",
    "EID":               "canonical_id",
    "OpenAlex ID":       "canonical_id",
    "Accession Number":  "canonical_id",
    "Record ID":         "canonical_id",
    "Local ID":          "canonical_id",
    "canonical_id":      "canonical_id",

    # entity_type synonyms
    "Type":              "entity_type",
    "Tipo":              "entity_type",
    "Tipo de entidad":   "entity_type",
    "Tipo de Entidad":   "entity_type",
    "Category":          "entity_type",
    "Categoría":         "entity_type",
    "Categoria":         "entity_type",
    "Clase":             "entity_type",
    "Class":             "entity_type",
    "Kind":              "entity_type",
    "Document Type":     "entity_type",
    "Tipo de documento": "entity_type",
    "Tipo de Documento": "entity_type",
    "Publication Type":  "entity_type",
    "Tipo de publicación": "entity_type",
    "Tipo de publicacion": "entity_type",
    "Subtype":           "entity_type",
    "entity_type":       "entity_type",

    # domain
    "Domain":            "domain",
    "domain":            "domain",

    # validation_status
    "Status":            "validation_status",
    "validation_status": "validation_status",

    # enrichment fields
    "enrichment_doi":              "enrichment_doi",
    "Citations":                   "enrichment_citation_count",
    "Citation Count":              "enrichment_citation_count",
    "enrichment_citation_count":   "enrichment_citation_count",
    "Concepts":                    "enrichment_concepts",
    "Keywords":                    "enrichment_concepts",
    "enrichment_concepts":         "enrichment_concepts",
    "enrichment_source":           "enrichment_source",
    "enrichment_status":           "enrichment_status",
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
