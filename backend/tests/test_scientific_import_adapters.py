import json

from backend.importers.scientific import detect_scientific_import


def test_openalex_json_import_adapter_maps_core_entities():
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "doi": "https://doi.org/10.1234/openalex",
                "display_name": "OpenAlex mapped publication",
                "publication_year": 2024,
                "type": "journal-article",
                "cited_by_count": 42,
                "primary_location": {
                    "source": {
                        "display_name": "Journal of Tests",
                        "host_organization_name": "Test Publisher",
                    }
                },
                "concepts": [{"display_name": "Semantic Web"}],
                "authorships": [
                    {
                        "author": {
                            "display_name": "Ada Lovelace",
                            "id": "https://openalex.org/A1",
                            "orcid": "https://orcid.org/0000-0001",
                        },
                        "institutions": [
                            {
                                "display_name": "University of Tests",
                                "id": "https://openalex.org/I1",
                                "country_code": "US",
                            }
                        ],
                    }
                ],
            }
        ]
    }

    result = detect_scientific_import("openalex.json", json.dumps(payload))

    assert result is not None
    assert result.provider == "openalex"
    publication = result.records[0]
    assert publication.provider_record_id == "https://openalex.org/W123"
    assert publication.doi == "10.1234/openalex"
    assert publication.authors[0].name == "Ada Lovelace"
    assert publication.affiliations[0].name == "University of Tests"
    entity = publication.to_entity_kwargs()
    attrs = json.loads(entity["attributes_json"])
    assert attrs["provider"] == "openalex"
    assert attrs["canonical_identifiers"][0]["scheme"] == "openalex"


def test_scopus_json_import_adapter_maps_core_entities():
    payload = {
        "search-results": {
            "entry": [
                {
                    "eid": "2-s2.0-123",
                    "dc:title": "Scopus mapped publication",
                    "prism:doi": "10.1234/scopus",
                    "prism:coverDate": "2023-05-01",
                    "prism:publicationName": "Scopus Journal",
                    "subtypeDescription": "Article",
                    "citedby-count": "7",
                    "author": [{"authname": "Grace Hopper", "authid": "700"}],
                }
            ]
        }
    }

    result = detect_scientific_import("scopus.json", json.dumps(payload))

    assert result is not None
    assert result.provider == "scopus"
    publication = result.records[0]
    assert publication.provider_record_id == "2-s2.0-123"
    assert publication.doi == "10.1234/scopus"
    assert publication.authors[0].name == "Grace Hopper"
    assert publication.citation_count == 7
