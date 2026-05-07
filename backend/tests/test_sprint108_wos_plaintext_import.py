"""
Sprint 108 — Plaintext scientific import compatibility.

Covers:
- parsing OpenAlex/WoS-style plaintext exports
- previewing `.txt` scientific uploads
- importing `.txt` scientific uploads into RawEntity
"""
import io
import json

from backend.parsers.science_mapper import science_record_to_entity
from backend.parsers.wos_plaintext_parser import looks_like_wos_plaintext, parse_wos_plaintext
from backend.importers.scientific import detect_scientific_import


WOS_PLAINTEXT_SAMPLE = """\
FN OpenAlex
VR 1.0
PT J
AU Christian Bizer
   Tom Heath
AF Christian Bizer
   Tom Heath
TI Linked Data - The Story So Far
SO International Journal on Semantic Web and Information Systems
LA English
DT Article
C3 Massachusetts Institute of Technology, US; Freie Universitat Berlin, DE
RP Christian Bizer (corresponding author), Freie Universitat Berlin, DE
RI Christian Bizer/https://openalex.org/A5076876024
OI Christian Bizer/0000-0003-2367-0237
CT 4551
NR 78
PU IGI Global
SN 1552-6283
PD JUL
PY 2009
VL 5
IS 3
BP 1
EP 22
DI 10.4018/jswis.2009081901
PG 22
OA closed
DA 2026-04-22
ER

PT B
AU Tom Heath
   Christian Bizer
AF Tom Heath
   Christian Bizer
TI Linked Data: Evolving the Web into a Global Data Space
SO Synthesis lectures on the semantic web
LA English
DT Book
C3 Freie Universitat Berlin, DE
CT 1630
NR 86
PU Morgan & Claypool Publishers
SN 2160-4711
PY 2011
DI 10.2200/s00334ed1v01y201102wbe001
OA bronze
DA 2026-04-22
ER
"""


class TestWosPlaintextParser:
    def test_detects_supported_plaintext_export(self):
        assert looks_like_wos_plaintext(WOS_PLAINTEXT_SAMPLE) is True

    def test_parses_records(self):
        records = parse_wos_plaintext(WOS_PLAINTEXT_SAMPLE)
        assert len(records) == 2

    def test_normalizes_core_fields(self):
        first = parse_wos_plaintext(WOS_PLAINTEXT_SAMPLE)[0]
        assert first["title"] == "Linked Data - The Story So Far"
        assert first["journal"] == "International Journal on Semantic Web and Information Systems"
        assert first["doi"] == "10.4018/jswis.2009081901"
        assert first["entity_type"] == "journal_article"
        assert first["citation_count"] == 4551
        assert "Christian Bizer" in first["authors"]
        assert "Tom Heath" in first["authors"]

    def test_science_mapper_keeps_citation_count(self):
        first = parse_wos_plaintext(WOS_PLAINTEXT_SAMPLE)[0]
        mapped = science_record_to_entity(first)
        assert mapped["enrichment_citation_count"] == 4551
        attrs = json.loads(mapped["attributes_json"])
        assert attrs["document_type"] == "Article"
        assert attrs["_source_name"] == "OpenAlex"
        assert attrs["_source_version"] == "1.0"
        assert attrs["raw_au"] == "Christian Bizer; Tom Heath"

    def test_wos_import_adapter_returns_canonical_publications(self):
        result = detect_scientific_import("works.txt", WOS_PLAINTEXT_SAMPLE)
        assert result is not None
        assert result.format == "wos_plaintext"
        assert result.provider == "wos"
        assert result.records[0].title == "Linked Data - The Story So Far"
        assert result.records[0].doi == "10.4018/jswis.2009081901"
        assert result.records[0].authors[0].name == "Christian Bizer"
        entity = result.records[0].to_entity_kwargs()
        attrs = json.loads(entity["attributes_json"])
        assert attrs["provider"] == "OpenAlex"
        assert attrs["mapping_version"] == "ukip-science-v1"
        assert attrs["canonical_authors"][0]["name"] == "Christian Bizer"


class TestWosPlaintextPreviewAndUpload:
    def test_preview_txt_as_science_format(self, client, editor_headers):
        response = client.post(
            "/upload/preview",
            files={"file": ("works.txt", io.BytesIO(WOS_PLAINTEXT_SAMPLE.encode("utf-8")), "text/plain")},
            headers=editor_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_science_format"] is True
        assert data["format"] == "wos_plaintext"
        assert data["row_count"] == 2
        assert data["auto_mapping"]["title"] == "primary_label"

    def test_upload_txt_imports_science_entities(self, client, editor_headers, db_session):
        from backend import models

        response = client.post(
            "/upload",
            files={"file": ("works.txt", io.BytesIO(WOS_PLAINTEXT_SAMPLE.encode("utf-8")), "text/plain")},
            headers=editor_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["total_rows"] == 2
        assert data["format"] == "wos_plaintext"
        assert data["provider"] == "wos"
        assert data["domain"] == "science"

        entities = db_session.query(models.RawEntity).order_by(models.RawEntity.id.asc()).all()
        assert len(entities) == 2
        assert entities[0].primary_label == "Linked Data - The Story So Far"
        assert entities[0].canonical_id == "10.4018/jswis.2009081901"
        assert entities[0].enrichment_citation_count == 4551
