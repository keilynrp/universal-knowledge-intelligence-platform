import json

from backend.importers.scientific import detect_scientific_import
from backend.parsers.science_mapper import science_record_to_entity
from backend.scripts.normalize_imported_text import normalize_entity
from backend.services.text_normalization import normalize_import_text, normalize_import_value


def test_normalize_import_text_strips_inline_html_and_footnote_markers():
    raw = "The Astropy Project &amp; Status<sup>*</sup>"

    assert normalize_import_text(raw) == "The Astropy Project & Status"


def test_normalize_import_text_preserves_meaningful_inline_content():
    raw = "<i>Open Science</i> &amp; Collaboration<br>Roadmap"

    assert normalize_import_text(raw) == "Open Science & Collaboration Roadmap"


def test_normalize_import_value_recurses_into_nested_provider_payloads():
    raw = {
        "title": "Alpha<sup>*</sup>",
        "topics": [{"display_name": "<b>Open Science</b>"}],
        "notes": ["A&amp;B"],
    }

    assert normalize_import_value(raw) == {
        "title": "Alpha",
        "topics": [{"display_name": "Open Science"}],
        "notes": ["A&B"],
    }


def test_science_mapper_persists_clean_primary_label_and_attributes():
    result = science_record_to_entity(
        {
            "title": "The Astropy Project<sup>*</sup>",
            "journal": "Astronomy &amp; Computing",
            "abstract": "<p>Open-source toolkit.</p>",
        }
    )
    attrs = json.loads(result["attributes_json"])

    assert result["primary_label"] == "The Astropy Project"
    assert attrs["journal"] == "Astronomy & Computing"
    assert attrs["abstract"] == "Open-source toolkit."


def test_scientific_adapter_persists_clean_raw_record_snapshot():
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "display_name": "HTML Title<sup>*</sup>",
                "publication_year": 2024,
                "type": "journal-article",
                "primary_location": {"source": {"display_name": "Journal &amp; Tests"}},
            }
        ]
    }

    result = detect_scientific_import("openalex.json", json.dumps(payload))

    assert result is not None
    entity = result.records[0].to_entity_kwargs()
    attrs = json.loads(entity["attributes_json"])
    assert entity["primary_label"] == "HTML Title"
    assert attrs["journal"] == "Journal & Tests"
    assert attrs["raw_record"]["display_name"] == "HTML Title"


def test_backfill_normalizes_existing_entity_payloads():
    class Entity:
        primary_label = "Legacy Title<sup>*</sup>"
        secondary_label = "Ada &amp; Grace"
        canonical_id = None
        enrichment_doi = None
        enrichment_concepts = None
        enrichment_source = None
        attributes_json = json.dumps({"journal": "<i>Open</i> &amp; Tests"})
        normalized_json = json.dumps({"note": "<p>Imported</p>"})

    entity = Entity()

    assert normalize_entity(entity) is True
    assert entity.primary_label == "Legacy Title"
    assert entity.secondary_label == "Ada & Grace"
    assert json.loads(entity.attributes_json)["journal"] == "Open & Tests"
    assert json.loads(entity.normalized_json)["note"] == "Imported"
