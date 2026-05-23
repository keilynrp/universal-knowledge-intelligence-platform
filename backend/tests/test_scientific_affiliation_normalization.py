import json
from unittest.mock import MagicMock, patch

from backend import models
from backend.adapters.enrichment.openalex import OpenAlexAdapter
from backend.analyzers.geographic import geographic_analysis
from backend.enrichment_worker import enrich_single_record
from backend.schemas_enrichment import AuthorAffiliation, CanonicalAffiliation, EnrichedRecord
from backend.services.scientific_affiliations import (
    extract_institution_authority_candidates,
    normalize_ror_id,
)


def test_enriched_record_supports_text_only_affiliations():
    record = EnrichedRecord(
        id="w1",
        title="Text affiliations",
        affiliations=["University of Tests, US"],
    )

    assert record.affiliations == ["University of Tests, US"]
    assert record.canonical_affiliations == []
    assert record.author_affiliations == []


def test_enriched_record_supports_structured_affiliations():
    institution = CanonicalAffiliation(
        name="University of Tests",
        ror="https://ror.org/03yrm5c26",
        openalex_id="https://openalex.org/I123",
        country_code="US",
        type="education",
        lineage=["https://openalex.org/I1"],
    )
    record = EnrichedRecord(
        id="w1",
        title="Structured affiliations",
        canonical_affiliations=[institution],
        author_affiliations=[
            AuthorAffiliation(
                author_name="Ada Lovelace",
                author_orcid="0000-0001-0000-0001",
                author_openalex_id="https://openalex.org/A123",
                author_position="first",
                author_order=1,
                institutions=[institution],
            )
        ],
    )

    assert record.canonical_affiliations[0].country_code == "US"
    assert record.author_affiliations[0].institutions[0].ror == "https://ror.org/03yrm5c26"


def test_openalex_parse_preserves_author_institution_relationships():
    raw = {
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.1234/test",
        "display_name": "Affiliation graph paper",
        "cited_by_count": 12,
        "publication_year": 2024,
        "authorships": [
            {
                "author_position": "first",
                "author": {
                    "id": "https://openalex.org/A1",
                    "display_name": "Ada Lovelace",
                    "orcid": "https://orcid.org/0000-0001-0000-0001",
                },
                "institutions": [
                    {
                        "id": "https://openalex.org/I1",
                        "display_name": "University of Tests",
                        "ror": "https://ror.org/03yrm5c26",
                        "country_code": "US",
                        "type": "education",
                        "lineage": ["https://openalex.org/IROOT"],
                    }
                ],
            },
            {
                "author_position": "last",
                "author": {"id": "https://openalex.org/A2", "display_name": "Grace Hopper"},
                "institutions": [
                    {
                        "id": "https://openalex.org/I1",
                        "display_name": "University of Tests",
                        "ror": "https://ror.org/03yrm5c26",
                        "country_code": "US",
                        "type": "education",
                    },
                    {
                        "id": "https://openalex.org/I2",
                        "display_name": "Open Science Lab",
                        "country_code": "GB",
                        "type": "facility",
                    },
                ],
            },
        ],
    }

    record = OpenAlexAdapter()._parse_record(raw)

    assert record.authors == ["Ada Lovelace", "Grace Hopper"]
    assert record.author_orcids == ["0000-0001-0000-0001", None]
    assert len(record.canonical_affiliations) == 2
    assert {aff.name for aff in record.canonical_affiliations} == {"University of Tests", "Open Science Lab"}
    assert record.author_affiliations[0].author_openalex_id == "https://openalex.org/A1"
    assert record.author_affiliations[0].author_position == "first"
    assert record.author_affiliations[0].author_order == 1
    assert record.author_affiliations[1].institutions[1].openalex_id == "https://openalex.org/I2"
    assert "University of Tests, US" in record.affiliations


def test_enrichment_worker_persists_structured_affiliations(db_session):
    entity = models.RawEntity(primary_label="Affiliation Paper", domain="science", enrichment_status="processing")
    db_session.add(entity)
    db_session.commit()

    institution = CanonicalAffiliation(
        name="University of Tests",
        ror="https://ror.org/03yrm5c26",
        openalex_id="https://openalex.org/I1",
        country_code="US",
        type="education",
    )
    enriched = EnrichedRecord(
        id="https://openalex.org/W123",
        title="Affiliation Paper",
        doi="10.1234/affiliation",
        authors=["Ada Lovelace"],
        author_orcids=["0000-0001-0000-0001"],
        affiliations=["University of Tests, US"],
        canonical_affiliations=[institution],
        author_affiliations=[
            AuthorAffiliation(
                author_name="Ada Lovelace",
                author_orcid="0000-0001-0000-0001",
                author_openalex_id="https://openalex.org/A1",
                author_position="first",
                author_order=1,
                institutions=[institution],
            )
        ],
        source_api="OpenAlex",
    )

    mock_openalex = MagicMock()
    mock_openalex.is_active = True
    mock_openalex.search_by_title.return_value = [enriched]
    mock_cb = MagicMock()
    mock_cb.call = lambda fn, *a, **kw: fn(*a, **kw)

    with (
        patch("backend.enrichment_worker._ACTIVE_CASCADE", ["openalex"]),
        patch("backend.enrichment_worker._PROVIDER_MAP", {"openalex": (mock_openalex, mock_cb)}),
    ):
        result = enrich_single_record(db_session, entity)

    attrs = json.loads(result.attributes_json)
    assert attrs["affiliations"] == ["University of Tests, US"]
    assert attrs["canonical_affiliations"][0]["country_code"] == "US"
    assert attrs["author_affiliations"][0]["author_openalex_id"] == "https://openalex.org/A1"


def test_ror_ready_candidate_extraction():
    attrs = {
        "canonical_affiliations": [
            {
                "name": "University of Tests",
                "ror": "https://ror.org/03yrm5c26",
                "openalex_id": "https://openalex.org/I1",
                "country_code": "US",
                "type": "education",
            },
            {
                "name": "OpenAlex Only Institute",
                "openalex_id": "https://openalex.org/I2",
                "country_code": "GB",
            },
        ]
    }

    candidates = extract_institution_authority_candidates(json.dumps(attrs))

    assert normalize_ror_id("https://ror.org/03yrm5c26") == "03yrm5c26"
    assert candidates[0]["ror"] == "03yrm5c26"
    assert candidates[0]["ror_url"] == "https://ror.org/03yrm5c26"
    assert candidates[1]["openalex_id"] == "https://openalex.org/I2"


def test_geographic_analysis_prefers_structured_affiliation_country(db_session):
    db_session.add(
        models.RawEntity(
            primary_label="Structured Geography",
            domain="structured_geo_test",
            enrichment_status="completed",
            attributes_json=json.dumps({
                "affiliation": "Unknown Lab, Somewhere",
                "canonical_affiliations": [
                    {"name": "University of Tests", "country_code": "MX"}
                ],
            }),
        )
    )
    db_session.commit()

    result = geographic_analysis("structured_geo_test")

    assert result["coverage"] == 1.0
    assert result["countries"][0]["country_code"] == "MX"
