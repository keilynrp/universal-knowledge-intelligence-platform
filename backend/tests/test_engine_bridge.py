"""Tests for engine_bridge — RawEntity → proto Publication conversion."""
import json
import pytest
from unittest.mock import MagicMock

from backend.proto.ukip.engine.v1 import engine_pb2
from backend.services.engine_bridge import (
    entity_to_publication,
    should_use_engine,
    shadow_mode_enabled,
    fallback_enabled,
    sync_threshold,
)


def _make_entity(
    *,
    entity_id: int = 1,
    primary_label: str = "Test Paper",
    enrichment_doi: str | None = "10.1234/test",
    enrichment_source: str | None = "openalex",
    enrichment_concepts: str | None = None,
    entity_type: str = "publication",
    attributes_json: dict | None = None,
) -> MagicMock:
    entity = MagicMock()
    entity.id = entity_id
    entity.primary_label = primary_label
    entity.enrichment_doi = enrichment_doi
    entity.enrichment_source = enrichment_source
    entity.enrichment_concepts = enrichment_concepts
    entity.entity_type = entity_type
    entity.attributes_json = json.dumps(attributes_json) if attributes_json is not None else None
    return entity


class TestEntityToPublication:
    """Uses real proto stubs — no proto mocking needed."""

    def test_entity_id_and_title(self):
        entity = _make_entity(entity_id=42, primary_label="Machine Learning Review")
        pub = entity_to_publication(entity)
        assert pub.entity_id == 42
        assert pub.title == "Machine Learning Review"

    def test_doi_set(self):
        entity = _make_entity(enrichment_doi="10.9999/hello")
        pub = entity_to_publication(entity)
        assert pub.doi == "10.9999/hello"
        assert pub.enrichment_doi == "10.9999/hello"

    def test_no_doi(self):
        entity = _make_entity(enrichment_doi=None)
        pub = entity_to_publication(entity)
        assert not pub.doi

    def test_enrichment_source(self):
        entity = _make_entity(enrichment_source="openalex")
        pub = entity_to_publication(entity)
        assert pub.enrichment_source == "openalex"

    def test_authors_converted(self):
        entity = _make_entity(
            attributes_json={
                "canonical_authors": [
                    {"name": "Alice Smith", "orcid": "0000-0001-2345-6789", "order": 1, "affiliations": ["MIT"]},
                    {"name": "Bob Jones", "order": 2, "affiliations": []},
                ]
            }
        )
        pub = entity_to_publication(entity)
        assert len(pub.authors) == 2
        assert pub.authors[0].name == "Alice Smith"
        assert pub.authors[0].orcid == "0000-0001-2345-6789"
        assert "MIT" in pub.authors[0].affiliations

    def test_affiliations_converted(self):
        entity = _make_entity(
            attributes_json={
                "canonical_affiliations": [
                    {"name": "MIT", "country": "US"},
                    {"name": "Oxford", "country": "UK"},
                ]
            }
        )
        pub = entity_to_publication(entity)
        assert len(pub.affiliations) == 2
        assert pub.affiliations[0].name == "MIT"
        assert pub.affiliations[0].country == "US"

    def test_identifiers_converted(self):
        entity = _make_entity(
            attributes_json={
                "canonical_identifiers": [
                    {"scheme": "doi", "value": "10.1234/test"},
                    {"scheme": "pmid", "value": "12345678"},
                ]
            }
        )
        pub = entity_to_publication(entity)
        assert len(pub.identifiers) == 2
        assert pub.identifiers[0].scheme == "doi"

    def test_identifiers_skip_incomplete(self):
        entity = _make_entity(
            attributes_json={
                "canonical_identifiers": [
                    {"scheme": "doi", "value": ""},      # empty value
                    {"scheme": "", "value": "12345"},    # empty scheme
                    {"scheme": "pmid", "value": "99"},   # valid
                ]
            }
        )
        pub = entity_to_publication(entity)
        assert len(pub.identifiers) == 1
        assert pub.identifiers[0].scheme == "pmid"

    def test_concepts_from_list(self):
        entity = _make_entity(
            attributes_json={"concepts": ["Machine Learning", "Neural Networks"]}
        )
        pub = entity_to_publication(entity)
        assert "Machine Learning" in pub.concepts
        assert "Neural Networks" in pub.concepts

    def test_concepts_from_csv_enrichment_concepts(self):
        entity = _make_entity(
            attributes_json={},
            enrichment_concepts="Machine Learning; Neural Networks, Deep Learning",
        )
        pub = entity_to_publication(entity)
        assert len(pub.concepts) == 3

    def test_year_from_attrs(self):
        entity = _make_entity(attributes_json={"year": 2023})
        pub = entity_to_publication(entity)
        assert pub.year == 2023

    def test_source_title_from_journal_key(self):
        entity = _make_entity(attributes_json={"journal": "Nature"})
        pub = entity_to_publication(entity)
        assert pub.source_title == "Nature"

    def test_authors_skip_empty_name(self):
        entity = _make_entity(
            attributes_json={
                "canonical_authors": [
                    {"name": "", "order": 1},   # empty name → skip
                    {"name": "Alice", "order": 2},
                ]
            }
        )
        pub = entity_to_publication(entity)
        assert len(pub.authors) == 1
        assert pub.authors[0].name == "Alice"

    def test_empty_attributes_json(self):
        entity = _make_entity(attributes_json=None)
        pub = entity_to_publication(entity)
        assert list(pub.authors) == []
        assert list(pub.affiliations) == []
        assert list(pub.identifiers) == []


class TestEngineBridgeHelpers:
    def test_should_use_engine_none(self):
        assert should_use_engine(None) is False

    def test_should_use_engine_with_client(self):
        assert should_use_engine(MagicMock()) is True

    def test_shadow_mode_default_off(self, monkeypatch):
        monkeypatch.delenv("ENGINE_SHADOW_MODE", raising=False)
        assert shadow_mode_enabled() is False

    def test_shadow_mode_on(self, monkeypatch):
        monkeypatch.setenv("ENGINE_SHADOW_MODE", "true")
        assert shadow_mode_enabled() is True

    def test_fallback_default_on(self, monkeypatch):
        monkeypatch.delenv("ENGINE_FALLBACK_PYTHON", raising=False)
        assert fallback_enabled() is True

    def test_sync_threshold_default(self, monkeypatch):
        monkeypatch.delenv("ENGINE_SYNC_THRESHOLD", raising=False)
        assert sync_threshold() == 500
