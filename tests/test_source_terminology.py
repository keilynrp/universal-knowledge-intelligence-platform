"""Tests for Task 1.5 — Source Terminology Contract."""
from backend.services.source_terminology import (
    SourceType,
    classify_field,
    get_source_label,
    get_section_key,
    assign_field_to_layer,
    group_fields_by_layer,
)


class TestSourceTypeEnum:
    def test_three_distinct_values(self):
        values = {e.value for e in SourceType}
        assert values == {"ingestion_source", "enrichment_provider", "authority_source"}

    def test_string_enum(self):
        assert SourceType.INGESTION_SOURCE == "ingestion_source"


class TestClassifyField:
    def test_ingestion_fields(self):
        assert classify_field("primary_label") == SourceType.INGESTION_SOURCE
        assert classify_field("domain") == SourceType.INGESTION_SOURCE
        assert classify_field("source") == SourceType.INGESTION_SOURCE

    def test_enrichment_fields(self):
        assert classify_field("enrichment_doi") == SourceType.ENRICHMENT_PROVIDER
        assert classify_field("enrichment_concepts") == SourceType.ENRICHMENT_PROVIDER
        assert classify_field("quality_score") == SourceType.ENRICHMENT_PROVIDER

    def test_authority_fields(self):
        assert classify_field("authority_source") == SourceType.AUTHORITY_SOURCE
        assert classify_field("confidence") == SourceType.AUTHORITY_SOURCE
        assert classify_field("resolution_status") == SourceType.AUTHORITY_SOURCE

    def test_unknown_field_defaults_to_ingestion(self):
        assert classify_field("some_random_field") == SourceType.INGESTION_SOURCE


class TestGetSourceLabel:
    def test_ingestion_label(self):
        key = get_source_label("primary_label")
        assert key == "provenance.source_type.ingestion_source"

    def test_enrichment_label(self):
        key = get_source_label("enrichment_doi")
        assert key == "provenance.source_type.enrichment_provider"

    def test_authority_label(self):
        key = get_source_label("authority_source")
        assert key == "provenance.source_type.authority_source"

    def test_override_with_value_type(self):
        key = get_source_label("primary_label", value_type="enrichment_provider")
        assert key == "provenance.source_type.enrichment_provider"

    def test_invalid_value_type_falls_back(self):
        key = get_source_label("enrichment_doi", value_type="bogus")
        assert key == "provenance.source_type.enrichment_provider"


class TestGetSectionKey:
    def test_section_keys(self):
        assert get_section_key("original_ingestion") == "provenance.section.original_ingestion"
        assert get_section_key("authority_audit") == "provenance.section.authority_audit"


class TestAssignFieldToLayer:
    def test_normalized_identity(self):
        assert assign_field_to_layer("primary_label") == "normalized_identity"
        assert assign_field_to_layer("canonical_id") == "normalized_identity"

    def test_original_ingestion(self):
        assert assign_field_to_layer("domain") == "original_ingestion"
        assert assign_field_to_layer("source") == "original_ingestion"

    def test_enrichment(self):
        assert assign_field_to_layer("enrichment_doi") == "external_enrichment"

    def test_authority(self):
        assert assign_field_to_layer("authority_source") == "authority_audit"


class TestGroupFieldsByLayer:
    def test_groups_correctly(self):
        fields = {
            "primary_label": "Test",
            "domain": "science",
            "enrichment_doi": "10.1234/test",
            "authority_source": "wikidata",
        }
        result = group_fields_by_layer(fields)
        assert "Test" == result["normalized_identity"]["primary_label"]
        assert "science" == result["original_ingestion"]["domain"]
        assert "10.1234/test" == result["external_enrichment"]["enrichment_doi"]
        assert "wikidata" == result["authority_audit"]["authority_source"]

    def test_empty_dict(self):
        result = group_fields_by_layer({})
        assert all(len(v) == 0 for v in result.values())

    def test_all_four_sections_present(self):
        result = group_fields_by_layer({"x": 1})
        assert set(result.keys()) == {
            "original_ingestion",
            "normalized_identity",
            "external_enrichment",
            "authority_audit",
        }
