from backend.adapters.enrichment.openalex import OpenAlexAdapter


def test_parse_record_captures_work_type():
    raw = {
        "id": "https://openalex.org/W1", "display_name": "A Book",
        "type": "book", "publication_year": 2020,
        "authorships": [], "primary_location": {},
    }
    rec = OpenAlexAdapter()._parse_record(raw)
    assert rec.work_type == "book"


def test_entity_response_schema_has_work_type():
    from backend.schemas import EntityBase
    assert "enrichment_work_type" in EntityBase.model_fields
