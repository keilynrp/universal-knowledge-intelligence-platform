"""Tests for authority_candidate_extraction.py — Task 3.5."""
import json
import pytest

from backend.services.authority_candidate_extraction import (
    AuthorityCandidate,
    AuthorityCandidateExtractor,
    CandidateFamily,
    CandidateOrigin,
)


def _entity(**kwargs) -> dict:
    base = {
        "primary_label": "Test Entity",
        "secondary_label": "",
        "enrichment_status": "pending",
        "attributes_json": "{}",
    }
    base.update(kwargs)
    return base


class TestPersonExtraction:
    def test_from_author_affiliations(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(
            enrichment_status="done",
            attributes_json=json.dumps({
                "author_affiliations": [
                    {"author_name": "Alice Smith", "orcid": "0000-0001-2345-6789"}
                ]
            }),
        )
        candidates = ext.extract(entity, entity_id=1)
        persons = [c for c in candidates if c.family == CandidateFamily.PERSON]
        assert len(persons) >= 1
        assert persons[0].label == "Alice Smith"
        assert persons[0].identifiers.get("orcid") == "0000-0001-2345-6789"
        assert persons[0].origin == CandidateOrigin.ENRICHMENT

    def test_from_secondary_label(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(secondary_label="Bob Jones, Carol Lee")
        candidates = ext.extract(entity)
        persons = [c for c in candidates if c.family == CandidateFamily.PERSON]
        assert len(persons) == 2

    def test_short_names_skipped(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(secondary_label="AB, Carol Lee")
        persons = [c for c in ext.extract(entity) if c.family == CandidateFamily.PERSON]
        assert len(persons) == 1
        assert persons[0].label == "Carol Lee"


class TestInstitutionExtraction:
    def test_from_canonical_affiliations(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(
            attributes_json=json.dumps({
                "canonical_affiliations": [
                    {"name": "MIT", "ror": "ror123", "openalex_id": "I1", "country_code": "US"}
                ]
            }),
        )
        candidates = ext.extract(entity)
        insts = [c for c in candidates if c.family == CandidateFamily.INSTITUTION]
        assert len(insts) == 1
        assert insts[0].label == "MIT"
        assert insts[0].identifiers["ror"] == "ror123"
        assert insts[0].confidence == 0.9  # has ROR

    def test_no_ror_lower_confidence(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(
            attributes_json=json.dumps({
                "canonical_affiliations": [{"name": "Lab X", "openalex_id": "I2"}]
            }),
        )
        insts = [c for c in ext.extract(entity) if c.family == CandidateFamily.INSTITUTION]
        assert insts[0].confidence == 0.6


class TestIdentifierExtraction:
    def test_doi(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(enrichment_doi="10.1234/test.paper")
        ids = [c for c in ext.extract(entity) if c.family == CandidateFamily.IDENTIFIER]
        doi_candidates = [c for c in ids if "doi" in c.identifiers]
        assert len(doi_candidates) == 1
        assert doi_candidates[0].confidence == 0.95

    def test_orcid_from_affiliations(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(
            attributes_json=json.dumps({
                "author_affiliations": [{"orcid": "0000-0001-2345-6789"}]
            }),
        )
        ids = [c for c in ext.extract(entity) if c.family == CandidateFamily.IDENTIFIER]
        orcid_candidates = [c for c in ids if "orcid" in c.identifiers]
        assert len(orcid_candidates) == 1

    def test_ror_from_affiliations(self):
        ext = AuthorityCandidateExtractor()
        # ROR regex requires format: 0[a-z0-9]{6}\d{2}
        entity = _entity(
            attributes_json=json.dumps({
                "canonical_affiliations": [{"ror": "0abcdef12"}]
            }),
        )
        ids = [c for c in ext.extract(entity) if c.family == CandidateFamily.IDENTIFIER]
        ror_candidates = [c for c in ids if "ror" in c.identifiers]
        assert len(ror_candidates) == 1


class TestPlaceExtraction:
    def test_country_from_affiliations(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(
            attributes_json=json.dumps({
                "canonical_affiliations": [
                    {"country_code": "US"},
                    {"country_code": "GB"},
                ]
            }),
        )
        places = [c for c in ext.extract(entity) if c.family == CandidateFamily.PLACE]
        assert len(places) == 2
        codes = {c.label for c in places}
        assert codes == {"US", "GB"}

    def test_dedup_countries(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(
            attributes_json=json.dumps({
                "canonical_affiliations": [
                    {"country_code": "US"},
                    {"country_code": "us"},
                ]
            }),
        )
        places = [c for c in ext.extract(entity) if c.family == CandidateFamily.PLACE]
        assert len(places) == 1


class TestVenueExtraction:
    def test_venue_with_issn(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(
            attributes_json=json.dumps({"venue": "Nature", "issn": "0028-0836"}),
        )
        venues = [c for c in ext.extract(entity) if c.family == CandidateFamily.VENUE]
        assert len(venues) == 1
        assert venues[0].confidence == 0.7

    def test_venue_without_issn(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(
            attributes_json=json.dumps({"venue": "Some Journal"}),
        )
        venues = [c for c in ext.extract(entity) if c.family == CandidateFamily.VENUE]
        assert venues[0].confidence == 0.5


class TestConceptExtraction:
    def test_from_enrichment_concepts(self):
        ext = AuthorityCandidateExtractor()
        # "AI" is only 2 chars so it's skipped by len>2 check
        entity = _entity(
            enrichment_concepts="Machine Learning, NLP, Artificial Intelligence",
            enrichment_status="done",
        )
        concepts = [c for c in ext.extract(entity) if c.family == CandidateFamily.CONCEPT]
        assert len(concepts) == 3

    def test_short_concepts_skipped(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(enrichment_concepts="ML, Natural Language Processing")
        concepts = [c for c in ext.extract(entity) if c.family == CandidateFamily.CONCEPT]
        assert len(concepts) == 1


class TestDeduplication:
    def test_dedup_by_key(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(
            enrichment_status="done",
            attributes_json=json.dumps({
                "author_affiliations": [
                    {"author_name": "Alice Smith"},
                    {"author_name": "alice smith"},
                ]
            }),
        )
        persons = [c for c in ext.extract(entity) if c.family == CandidateFamily.PERSON]
        # Both should dedup to one (same name lowered)
        assert len(persons) == 1

    def test_higher_confidence_wins(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(
            enrichment_status="done",
            attributes_json=json.dumps({
                "author_affiliations": [
                    {"author_name": "Alice Smith"},
                    {"author_name": "Alice Smith", "orcid": "0000-0001-2345-6789"},
                ]
            }),
        )
        persons = [c for c in ext.extract(entity) if c.family == CandidateFamily.PERSON]
        # The one with ORCID should win (higher confidence)
        matched = [p for p in persons if p.identifiers.get("orcid")]
        assert len(matched) >= 1


class TestToDict:
    def test_serialization(self):
        ext = AuthorityCandidateExtractor()
        entity = _entity(enrichment_doi="10.1234/test")
        candidates = ext.extract(entity)
        for c in candidates:
            d = c.to_dict()
            assert isinstance(d["family"], str)
            assert isinstance(d["origin"], str)
