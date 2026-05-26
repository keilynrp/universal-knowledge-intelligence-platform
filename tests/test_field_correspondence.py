"""Tests for the source-agnostic field correspondence layer."""

from backend.services.field_correspondence import (
    infer_source_schema,
    resolve_field_correspondence,
    resolve_field_mapping,
)


def test_identifier_value_maps_to_canonical_id_with_scheme():
    correspondence = resolve_field_correspondence("DOI")

    assert correspondence is not None
    assert correspondence.semantic_concept == "persistent_identifier"
    assert correspondence.canonical_target == "canonical_id"
    assert correspondence.identifier_scheme == "doi"
    assert correspondence.requires_review is False


def test_identifier_scheme_header_does_not_map_to_canonical_id():
    correspondence = resolve_field_correspondence("Tipo de Identificador")

    assert correspondence is not None
    assert correspondence.semantic_concept == "identifier_scheme"
    assert correspondence.canonical_target is None
    assert resolve_field_mapping("Tipo de Identificador") is None


def test_entity_type_header_maps_to_entity_type():
    assert resolve_field_mapping("Tipo de entidad") == "entity_type"


def test_generic_id_maps_with_review_required_metadata():
    correspondence = resolve_field_correspondence("ID")

    assert correspondence is not None
    assert correspondence.canonical_target == "canonical_id"
    assert correspondence.identifier_scheme is None
    assert correspondence.requires_review is True


def test_wos_short_code_requires_source_schema():
    assert resolve_field_mapping("DI") is None

    correspondence = resolve_field_correspondence("DI", source_schema="wos")
    assert correspondence is not None
    assert correspondence.canonical_target == "canonical_id"
    assert correspondence.identifier_scheme == "doi"
    assert "wos_schema_rule" in correspondence.evidence


def test_openalex_id_is_not_canonical_id_under_openalex_schema():
    correspondence = resolve_field_correspondence("id", source_schema="openalex")

    assert correspondence is not None
    assert correspondence.semantic_concept == "external_authority_id"
    assert correspondence.canonical_target is None
    assert correspondence.identifier_scheme == "openalex"


def test_infer_source_schema_from_wos_fields():
    assert infer_source_schema(fields={"FN", "VR", "TI", "DI", "DT"}) == "wos"
