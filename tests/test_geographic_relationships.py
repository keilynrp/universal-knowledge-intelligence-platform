"""Tests for geographic_relationships.py — Task 3.4."""
import pytest

from backend.services.geographic_relationships import (
    GeoRelationship,
    GeoRelationshipMaterializer,
    GeoRelationType,
)


class TestInstitutionLocation:
    def test_basic(self):
        m = GeoRelationshipMaterializer()
        rel = m.materialize_institution_location("MIT", "us", entity_id=1)
        assert rel.id == 1
        assert rel.source_entity_type == "organization"
        assert rel.target_country_code == "US"
        assert rel.relation_type == GeoRelationType.LOCATED_IN
        assert rel.confidence == 0.95

    def test_with_ror(self):
        m = GeoRelationshipMaterializer()
        rel = m.materialize_institution_location("MIT", "US", ror_id="0abcde12")
        assert "ror_id:0abcde12" in rel.evidence

    def test_custom_confidence(self):
        m = GeoRelationshipMaterializer()
        rel = m.materialize_institution_location("X", "GB", confidence=0.7)
        assert rel.confidence == 0.7

    def test_stored_in_list(self):
        m = GeoRelationshipMaterializer()
        m.materialize_institution_location("A", "US")
        m.materialize_institution_location("B", "GB")
        assert len(m.relationships) == 2


class TestPublicationAssociation:
    def test_single_country(self):
        m = GeoRelationshipMaterializer()
        rels = m.materialize_publication_association(10, ["US"])
        assert len(rels) == 1
        assert rels[0].relation_type == GeoRelationType.ASSOCIATED_WITH
        assert rels[0].source_entity_type == "publication"

    def test_multiple_countries(self):
        m = GeoRelationshipMaterializer()
        rels = m.materialize_publication_association(10, ["US", "GB", "DE"])
        assert len(rels) == 3

    def test_dedup_countries(self):
        m = GeoRelationshipMaterializer()
        rels = m.materialize_publication_association(10, ["US", "us", " US "])
        assert len(rels) == 1

    def test_empty_codes_skipped(self):
        m = GeoRelationshipMaterializer()
        rels = m.materialize_publication_association(10, ["", " ", "US"])
        assert len(rels) == 1

    def test_sequential_ids(self):
        m = GeoRelationshipMaterializer()
        rels = m.materialize_publication_association(10, ["US", "GB"])
        assert rels[0].id == 1
        assert rels[1].id == 2


class TestDatasetCoverage:
    def test_basic(self):
        m = GeoRelationshipMaterializer()
        rels = m.materialize_dataset_coverage(20, ["US", "MX"])
        assert len(rels) == 2
        assert all(r.relation_type == GeoRelationType.COVERS_REGION for r in rels)
        assert all(r.source_entity_type == "dataset" for r in rels)

    def test_dedup(self):
        m = GeoRelationshipMaterializer()
        rels = m.materialize_dataset_coverage(20, ["mx", "MX"])
        assert len(rels) == 1


class TestQueries:
    def test_get_by_entity(self):
        m = GeoRelationshipMaterializer()
        m.materialize_institution_location("MIT", "US", entity_id=1)
        m.materialize_publication_association(2, ["GB"])
        assert len(m.get_relationships_for_entity(1)) == 1
        assert len(m.get_relationships_for_entity(2)) == 1
        assert len(m.get_relationships_for_entity(99)) == 0

    def test_get_by_country(self):
        m = GeoRelationshipMaterializer()
        m.materialize_institution_location("MIT", "US", entity_id=1)
        m.materialize_publication_association(2, ["US", "GB"])
        assert len(m.get_relationships_by_country("US")) == 2
        assert len(m.get_relationships_by_country("GB")) == 1
        assert len(m.get_relationships_by_country("DE")) == 0

    def test_to_dict(self):
        m = GeoRelationshipMaterializer()
        rel = m.materialize_institution_location("MIT", "US")
        d = rel.to_dict()
        assert d["relation_type"] == "located_in"
        assert d["target_country_code"] == "US"
