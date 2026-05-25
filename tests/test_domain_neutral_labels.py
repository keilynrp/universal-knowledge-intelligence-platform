"""Tests for domain_neutral_labels.py — Tasks 5.1 + 5.3."""
import os
import pytest

from backend.services.domain_neutral_labels import (
    get_all_field_metadata,
    get_destructive_dialog_copy,
    get_field_examples,
    get_field_help,
    get_field_label,
)


class TestNeutralLabels:
    def test_primary_label_en(self):
        assert get_field_label("primary_label", "en") == "Primary label"

    def test_primary_label_es(self):
        assert get_field_label("primary_label", "es") == "Etiqueta primaria"

    def test_unknown_field_returns_name(self):
        assert get_field_label("unknown_field", "en") == "unknown_field"

    def test_help_mentions_doi(self):
        help_text = get_field_help("canonical_id", "en")
        assert "DOI" in help_text

    def test_help_mentions_orcid(self):
        help_text = get_field_help("canonical_id", "en")
        assert "ORCID" in help_text

    def test_examples_no_sku_default(self):
        examples = get_field_examples("canonical_id", "en")
        assert "SKU" not in examples
        assert "DOI" in examples

    def test_entity_type_examples_neutral(self):
        examples = get_field_examples("entity_type", "en")
        assert "person" in examples.lower()
        assert "organization" in examples.lower()
        assert "product" not in examples.lower()

    def test_secondary_label_neutral(self):
        examples = get_field_examples("secondary_label", "en")
        assert "brand" not in examples.lower()
        assert "author" in examples.lower()


class TestCommerceOverride:
    def test_commerce_domain_shows_sku(self, monkeypatch):
        monkeypatch.setenv("ENABLE_COMMERCE_ADAPTERS", "true")
        examples = get_field_examples("canonical_id", "en", domain="commerce")
        assert "SKU" in examples

    def test_commerce_domain_product_label(self, monkeypatch):
        monkeypatch.setenv("ENABLE_COMMERCE_ADAPTERS", "true")
        help_text = get_field_help("primary_label", "en", domain="commerce")
        assert "product" in help_text.lower()

    def test_science_domain_ignores_commerce(self, monkeypatch):
        monkeypatch.setenv("ENABLE_COMMERCE_ADAPTERS", "true")
        examples = get_field_examples("canonical_id", "en", domain="science")
        assert "SKU" not in examples
        assert "DOI" in examples

    def test_commerce_disabled_no_commerce_labels(self, monkeypatch):
        monkeypatch.setenv("ENABLE_COMMERCE_ADAPTERS", "false")
        examples = get_field_examples("canonical_id", "en", domain="commerce")
        assert "SKU" not in examples


class TestDestructiveDialogs:
    def test_en_neutral(self):
        copy = get_destructive_dialog_copy("en")
        assert "records" in copy["delete_all_body"].lower()
        assert "products" not in copy["delete_all_body"].lower()
        assert copy["export_filename"] == "export_entities"

    def test_es_neutral(self):
        copy = get_destructive_dialog_copy("es")
        assert "registros" in copy["delete_all_body"].lower()
        assert copy["export_filename"] == "exportar_entidades"


class TestGetAllMetadata:
    def test_returns_all_fields(self):
        metadata = get_all_field_metadata("en")
        assert "primary_label" in metadata
        assert "secondary_label" in metadata
        assert "canonical_id" in metadata
        assert "entity_type" in metadata
        for field_meta in metadata.values():
            assert "label" in field_meta
            assert "help" in field_meta
            assert "examples" in field_meta
