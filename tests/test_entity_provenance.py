"""Tests for Task 2.6 — Entity Provenance Layering."""
import json

from backend.services.entity_provenance import (
    EntityDetailLayered,
    build_layered_detail,
    get_provenance_badge,
)
from backend.services.source_terminology import SourceType


class TestBuildLayeredDetail:
    def test_separation_of_layers(self):
        entity = {
            "id": 1,
            "primary_label": "Test Paper",
            "secondary_label": "Author A",
            "canonical_id": "CAN-001",
            "domain": "science",
            "source": "upload",
            "enrichment_doi": "10.1234/test",
            "enrichment_citation_count": 42,
            "enrichment_status": "done",
            "quality_score": 0.85,
        }
        detail = build_layered_detail(1, entity)

        assert "primary_label" in detail.normalized_identity
        assert "secondary_label" in detail.normalized_identity
        assert "canonical_id" in detail.normalized_identity

        assert "domain" in detail.original_ingestion
        assert "source" in detail.original_ingestion

        assert "enrichment_doi" in detail.external_enrichment
        assert "enrichment_citation_count" in detail.external_enrichment
        assert "quality_score" in detail.external_enrichment

    def test_authority_records(self):
        entity = {"id": 2, "primary_label": "Test"}
        authority = [
            {"authority_source": "wikidata", "canonical_label": "Test Entity", "confidence": 0.95}
        ]
        detail = build_layered_detail(2, entity, authority_records=authority)
        assert "records" in detail.authority_audit
        assert len(detail.authority_audit["records"]) == 1

    def test_ingestion_only(self):
        entity = {
            "id": 3,
            "primary_label": "Simple Upload",
            "domain": "default",
            "source": "user",
        }
        detail = build_layered_detail(3, entity)
        assert detail.normalized_identity["primary_label"] == "Simple Upload"
        assert detail.original_ingestion["domain"] == "default"
        assert len(detail.external_enrichment) == 0
        assert len(detail.authority_audit) == 0

    def test_attributes_json_expansion(self):
        attrs = {"year": "2023", "publisher": "Springer", "canonical_affiliations": [{"name": "MIT"}]}
        entity = {
            "id": 4,
            "primary_label": "Paper",
            "attributes_json": json.dumps(attrs),
        }
        detail = build_layered_detail(4, entity)
        # canonical_affiliations goes to enrichment
        assert "canonical_affiliations" in detail.external_enrichment
        # regular attrs go to ingestion
        assert "attr.year" in detail.original_ingestion

    def test_to_dict(self):
        detail = EntityDetailLayered(entity_id=5)
        d = detail.to_dict()
        assert d["entity_id"] == 5
        assert "original_ingestion" in d
        assert "normalized_identity" in d
        assert "external_enrichment" in d
        assert "authority_audit" in d


class TestProvenanceBadge:
    def test_ingestion_badge(self):
        badge = get_provenance_badge("domain")
        assert badge.source_type == SourceType.INGESTION_SOURCE
        assert badge.section == "original_ingestion"

    def test_enrichment_badge(self):
        badge = get_provenance_badge("enrichment_doi")
        assert badge.source_type == SourceType.ENRICHMENT_PROVIDER
        assert badge.section == "external_enrichment"

    def test_authority_badge(self):
        badge = get_provenance_badge("authority_source")
        assert badge.source_type == SourceType.AUTHORITY_SOURCE
        assert badge.section == "authority_audit"

    def test_normalized_identity_badge(self):
        badge = get_provenance_badge("primary_label")
        assert badge.section == "normalized_identity"
