"""Domain-Neutral Labels — Tasks 5.1 + 5.3.

Provides domain-neutral label mappings for the import wizard and
entity detail, replacing commerce-specific terminology with
research/knowledge-domain-neutral alternatives.
"""
from __future__ import annotations

from typing import Any

from backend.services.feature_flags import commerce_adapters_enabled


# Neutral label mappings for core fields
_NEUTRAL_LABELS: dict[str, dict[str, str]] = {
    "primary_label": {
        "en": "Primary label",
        "es": "Etiqueta primaria",
        "help_en": "The main name or title (e.g., publication title, person name, dataset title)",
        "help_es": "El nombre o título principal (ej., título de publicación, nombre de persona, título de dataset)",
        "examples_en": "Publication title, Person name, Dataset title",
        "examples_es": "Título de publicación, Nombre de persona, Título de dataset",
    },
    "secondary_label": {
        "en": "Secondary label",
        "es": "Etiqueta secundaria",
        "help_en": "Supporting label (e.g., authors, institution, venue)",
        "help_es": "Etiqueta de apoyo (ej., autores, institución, revista)",
        "examples_en": "Author names, Institution, Venue",
        "examples_es": "Nombres de autores, Institución, Revista",
    },
    "canonical_id": {
        "en": "Canonical identifier",
        "es": "Identificador canónico",
        "help_en": "A persistent identifier (e.g., DOI, ORCID, ROR, ISBN)",
        "help_es": "Un identificador persistente (ej., DOI, ORCID, ROR, ISBN)",
        "examples_en": "DOI, ORCID, ROR, ISBN, ISSN",
        "examples_es": "DOI, ORCID, ROR, ISBN, ISSN",
    },
    "entity_type": {
        "en": "Entity type",
        "es": "Tipo de entidad",
        "help_en": "Category of the record (e.g., person, organization, publication, dataset)",
        "help_es": "Categoría del registro (ej., persona, organización, publicación, dataset)",
        "examples_en": "Person, Organization, Publication, Dataset, Concept",
        "examples_es": "Persona, Organización, Publicación, Dataset, Concepto",
    },
}

# Commerce-specific labels (only shown when ENABLE_COMMERCE_ADAPTERS=true)
_COMMERCE_LABELS: dict[str, dict[str, str]] = {
    "primary_label": {
        "en": "Product name",
        "es": "Nombre de producto",
        "help_en": "The product or item name (e.g., SKU description, brand name)",
        "help_es": "El nombre del producto o artículo (ej., descripción de SKU, nombre de marca)",
        "examples_en": "Product name, Brand, SKU description",
        "examples_es": "Nombre de producto, Marca, Descripción de SKU",
    },
    "canonical_id": {
        "en": "Product identifier",
        "es": "Identificador de producto",
        "help_en": "A unique product code (e.g., SKU, barcode, EAN)",
        "help_es": "Un código único de producto (ej., SKU, código de barras, EAN)",
        "examples_en": "SKU, Barcode, EAN, UPC",
        "examples_es": "SKU, Código de barras, EAN, UPC",
    },
}


def get_field_label(field_name: str, lang: str = "en", domain: str | None = None) -> str:
    """Get the display label for a field."""
    labels = _NEUTRAL_LABELS.get(field_name, {})
    return labels.get(lang, field_name)


def get_field_help(field_name: str, lang: str = "en", domain: str | None = None) -> str:
    """Get the help text for a field, respecting domain context."""
    # Commerce labels only if adapters are enabled AND domain is commerce
    if domain == "commerce" and commerce_adapters_enabled():
        commerce = _COMMERCE_LABELS.get(field_name, {})
        if commerce:
            return commerce.get(f"help_{lang}", "")

    labels = _NEUTRAL_LABELS.get(field_name, {})
    return labels.get(f"help_{lang}", "")


def get_field_examples(field_name: str, lang: str = "en", domain: str | None = None) -> str:
    """Get example values for a field."""
    if domain == "commerce" and commerce_adapters_enabled():
        commerce = _COMMERCE_LABELS.get(field_name, {})
        if commerce:
            return commerce.get(f"examples_{lang}", "")

    labels = _NEUTRAL_LABELS.get(field_name, {})
    return labels.get(f"examples_{lang}", "")


def get_all_field_metadata(lang: str = "en", domain: str | None = None) -> dict[str, dict[str, str]]:
    """Get all field metadata for import wizard / entity detail."""
    result: dict[str, dict[str, str]] = {}
    for field_name in _NEUTRAL_LABELS:
        result[field_name] = {
            "label": get_field_label(field_name, lang, domain),
            "help": get_field_help(field_name, lang, domain),
            "examples": get_field_examples(field_name, lang, domain),
        }
    return result


def get_destructive_dialog_copy(lang: str = "en") -> dict[str, str]:
    """Get neutral copy for destructive dialogs."""
    if lang == "es":
        return {
            "delete_all_title": "Eliminar todos los registros",
            "delete_all_body": "¿Estás seguro de que deseas eliminar todos los registros/entidades? Esta acción no se puede deshacer.",
            "delete_single_title": "Eliminar registro",
            "delete_single_body": "¿Estás seguro de que deseas eliminar este registro?",
            "export_filename": "exportar_entidades",
        }
    return {
        "delete_all_title": "Delete all records",
        "delete_all_body": "Are you sure you want to delete all records/entities? This action cannot be undone.",
        "delete_single_title": "Delete record",
        "delete_single_body": "Are you sure you want to delete this record?",
        "export_filename": "export_entities",
    }
