"""Tests for jsonld_exporter.py — Task 4.7."""
import json
import pytest

from backend.exporters.jsonld_exporter import (
    JSONLDExporter,
    LinkedDataExport,
)


def _entity(**kwargs) -> dict:
    base = {
        "id": 1,
        "primary_label": "Test Publication",
        "secondary_label": "Author et al.",
        "entity_type": "publication",
        "enrichment_doi": "10.1234/test",
        "enrichment_concepts": "Machine Learning, NLP",
        "attributes_json": "{}",
    }
    base.update(kwargs)
    return base


class TestBasicExport:
    def test_schema_org_publication(self):
        exporter = JSONLDExporter()
        result = exporter.export_entity(_entity())
        doc = result.document
        assert doc["@type"] == "ScholarlyArticle"
        assert doc["name"] == "Test Publication"
        assert doc["@id"] == "https://doi.org/10.1234/test"

    def test_identifier_property_value(self):
        exporter = JSONLDExporter()
        doc = exporter.export_entity(_entity()).document
        assert doc["identifier"]["propertyID"] == "DOI"
        assert doc["identifier"]["value"] == "10.1234/test"

    def test_concepts_as_about(self):
        exporter = JSONLDExporter()
        doc = exporter.export_entity(_entity()).document
        assert len(doc["about"]) == 2
        assert doc["about"][0]["@type"] == "DefinedTerm"

    def test_context_present(self):
        exporter = JSONLDExporter()
        doc = exporter.export_entity(_entity()).document
        assert "@context" in doc
        assert "@vocab" in doc["@context"]

    def test_provenance_included(self):
        exporter = JSONLDExporter()
        doc = exporter.export_entity(_entity()).document
        assert doc["sdPublisher"]["name"] == "UKIP"

    def test_provenance_excluded(self):
        exporter = JSONLDExporter()
        doc = exporter.export_entity(_entity(), include_provenance=False).document
        assert "sdPublisher" not in doc


class TestVocabularyAlignments:
    def test_bibframe(self):
        exporter = JSONLDExporter()
        result = exporter.export_entity(_entity(), vocabulary="bibframe")
        assert result.document["@type"] == "bf:Work"
        assert result.warnings == []

    def test_edm(self):
        exporter = JSONLDExporter()
        result = exporter.export_entity(_entity(), vocabulary="edm")
        assert result.document["@type"] == "edm:ProvidedCHO"

    def test_dataset_dcat(self):
        exporter = JSONLDExporter()
        result = exporter.export_entity(_entity(entity_type="dataset"), vocabulary="dcat")
        assert result.document["@type"] == "dcat:Dataset"

    def test_fallback_with_warning(self):
        exporter = JSONLDExporter()
        result = exporter.export_entity(_entity(entity_type="concept"), vocabulary="dcat")
        assert len(result.warnings) == 1
        assert "falling back" in result.warnings[0].lower()

    def test_person_schema_org(self):
        exporter = JSONLDExporter()
        result = exporter.export_entity(_entity(entity_type="person"))
        assert result.document["@type"] == "Person"


class TestAuthority:
    def test_wikidata_same_as(self):
        exporter = JSONLDExporter()
        entity = _entity(authority_source="wikidata", authority_id="Q12345")
        doc = exporter.export_entity(entity).document
        assert "https://www.wikidata.org/entity/Q12345" in doc["sameAs"]

    def test_orcid_same_as(self):
        exporter = JSONLDExporter()
        entity = _entity(authority_source="orcid", authority_id="0000-0001-2345-6789")
        doc = exporter.export_entity(entity).document
        assert "https://orcid.org/0000-0001-2345-6789" in doc["sameAs"]

    def test_viaf_same_as(self):
        exporter = JSONLDExporter()
        entity = _entity(authority_source="viaf", authority_id="12345678")
        doc = exporter.export_entity(entity).document
        assert "https://viaf.org/viaf/12345678" in doc["sameAs"]


class TestAffiliations:
    def test_affiliations_exported(self):
        exporter = JSONLDExporter()
        entity = _entity(attributes_json=json.dumps({
            "canonical_affiliations": [
                {"name": "MIT", "ror": "03v76x132", "country_code": "US"}
            ]
        }))
        doc = exporter.export_entity(entity).document
        assert len(doc["affiliation"]) == 1
        aff = doc["affiliation"][0]
        assert aff["@type"] == "Organization"
        assert aff["name"] == "MIT"
        assert aff["sameAs"] == "https://ror.org/03v76x132"
        assert aff["addressCountry"] == "US"


class TestGeographic:
    def test_geo_entity_export(self):
        exporter = JSONLDExporter()
        geo = {
            "id": 10,
            "name": "Switzerland",
            "country_code": "CH",
            "latitude": 46.8,
            "longitude": 8.2,
            "wikidata_id": "Q39",
            "geonames_id": "2658434",
        }
        result = exporter.export_geographic(geo)
        doc = result.document
        assert doc["@type"] == "Place"
        assert doc["name"] == "Switzerland"
        assert doc["addressCountry"] == "CH"
        assert doc["geo"]["latitude"] == 46.8
        assert doc["sameAs"] == "https://www.wikidata.org/entity/Q39"
        assert doc["identifier"]["propertyID"] == "GeoNames"

    def test_geo_without_coords(self):
        exporter = JSONLDExporter()
        result = exporter.export_geographic({"name": "Unknown Place"})
        assert "geo" not in result.document


class TestSerialization:
    def test_to_json(self):
        exporter = JSONLDExporter()
        result = exporter.export_entity(_entity())
        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert parsed["@type"] == "ScholarlyArticle"

    def test_canonical_id_used(self):
        exporter = JSONLDExporter()
        entity = _entity(canonical_id="urn:ukip:123")
        doc = exporter.export_entity(entity).document
        assert doc["@id"] == "urn:ukip:123"
