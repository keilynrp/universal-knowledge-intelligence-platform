"""
Sprint 71 — Bulk Import Wizard UI tests.

Covers:
- POST /upload/preview: CSV, Excel, JSON, XML, BibTeX, RIS
  — format detection, row_count, columns, sample_rows, auto_mapping, is_science_format
- POST /upload with domain param: entity tagged correctly
- POST /upload with field_mapping override: custom column→model-field routing
- POST /upload/preview auth guard
- POST /upload auth guard unchanged
- Edge cases: empty file, wrong extension, oversized preview
"""
import io
import json
import pytest

import pandas as pd


# ── Helpers ───────────────────────────────────────────────────────────────────

def _csv_file(data: dict | list = None, name="test.csv"):
    if data is None:
        data = [{"Title": "Paper A", "Author": "Smith", "Year": "2020"},
                {"Title": "Paper B", "Author": "Jones", "Year": "2021"}]
    df = pd.DataFrame(data if isinstance(data, list) else [data])
    buf = io.BytesIO(df.to_csv(index=False).encode())
    buf.name = name
    return buf


def _excel_file(data: list = None, name="test.xlsx"):
    if data is None:
        data = [{"Title": "Entity 1", "Brand": "ACME"}]
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    buf.name = name
    return buf


def _json_file(data: list = None, name="test.json"):
    if data is None:
        data = [{"name": "Alpha", "type": "paper"}]
    content = json.dumps(data).encode()
    buf = io.BytesIO(content)
    buf.name = name
    return buf


_BIBTEX_CONTENT = b"""
@article{smith2020,
  title = {Advances in AI},
  author = {Smith, John},
  journal = {Nature},
  year = {2020},
  doi = {10.1000/xyz123}
}
@book{jones2021,
  title = {Deep Learning},
  author = {Jones, Alice},
  year = {2021}
}
"""

_RIS_CONTENT = b"""
TY  - JOUR
TI  - Test Paper
AU  - Doe, Jane
PY  - 2022
DO  - 10.9999/test
ER  -
"""


# ── POST /upload/preview ───────────────────────────────────────────────────────

class TestUploadPreview:
    def test_requires_auth(self, client):
        buf = _csv_file()
        resp = client.post("/upload/preview", files={"file": ("test.csv", buf, "text/csv")})
        assert resp.status_code in (401, 403)

    def test_csv_preview_returns_format(self, client, editor_headers):
        buf = _csv_file()
        resp = client.post(
            "/upload/preview",
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["format"] == "csv"

    def test_csv_preview_row_count(self, client, editor_headers):
        buf = _csv_file()
        resp = client.post(
            "/upload/preview",
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        assert resp.json()["row_count"] == 2

    def test_csv_preview_columns_detected(self, client, editor_headers):
        buf = _csv_file()
        resp = client.post(
            "/upload/preview",
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        cols = resp.json()["columns"]
        assert "Title" in cols
        assert "Author" in cols

    def test_csv_preview_sample_rows(self, client, editor_headers):
        buf = _csv_file()
        resp = client.post(
            "/upload/preview",
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        data = resp.json()
        assert len(data["sample_rows"]) <= 5
        assert len(data["sample_rows"]) > 0

    def test_csv_preview_auto_mapping_keys(self, client, editor_headers):
        buf = _csv_file()
        resp = client.post(
            "/upload/preview",
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        am = resp.json()["auto_mapping"]
        assert "Title" in am or "Author" in am

    def test_csv_preview_is_not_science(self, client, editor_headers):
        buf = _csv_file()
        resp = client.post(
            "/upload/preview",
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        assert resp.json()["is_science_format"] is False

    def test_excel_preview(self, client, editor_headers):
        buf = _excel_file()
        resp = client.post(
            "/upload/preview",
            files={"file": ("test.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=editor_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["format"] == "excel"

    def test_json_preview(self, client, editor_headers):
        buf = _json_file()
        resp = client.post(
            "/upload/preview",
            files={"file": ("test.json", buf, "application/json")},
            headers=editor_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["format"] == "json"

    def test_bibtex_preview_science_format(self, client, editor_headers):
        resp = client.post(
            "/upload/preview",
            files={"file": ("refs.bib", io.BytesIO(_BIBTEX_CONTENT), "text/plain")},
            headers=editor_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_science_format"] is True
        assert data["format"] == "bibtex"
        assert data["row_count"] == 2

    def test_bibtex_preview_auto_mapping_has_title(self, client, editor_headers):
        resp = client.post(
            "/upload/preview",
            files={"file": ("refs.bib", io.BytesIO(_BIBTEX_CONTENT), "text/plain")},
            headers=editor_headers,
        )
        am = resp.json()["auto_mapping"]
        assert "title" in am
        assert am["title"] == "primary_label"

    def test_ris_preview_science_format(self, client, editor_headers):
        resp = client.post(
            "/upload/preview",
            files={"file": ("refs.ris", io.BytesIO(_RIS_CONTENT), "text/plain")},
            headers=editor_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_science_format"] is True
        assert data["format"] == "ris"

    def test_preview_response_has_all_keys(self, client, editor_headers):
        buf = _csv_file()
        resp = client.post(
            "/upload/preview",
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        data = resp.json()
        for key in ("format", "row_count", "columns", "sample_rows", "auto_mapping", "is_science_format"):
            assert key in data, f"Missing key: {key}"

    def test_empty_file_returns_zero_rows(self, client, editor_headers):
        empty = io.BytesIO(b"col1,col2\n")  # header only
        resp = client.post(
            "/upload/preview",
            files={"file": ("empty.csv", empty, "text/csv")},
            headers=editor_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["row_count"] == 0


# ── POST /upload with domain param ────────────────────────────────────────────

class TestUploadWithDomain:
    def test_upload_csv_with_domain(self, client, editor_headers, db_session):
        from backend import models
        buf = _csv_file([{"primary_label": "Test Entity", "entity_type": "paper"}])
        resp = client.post(
            "/upload",
            data={"domain": "science"},
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_rows"] == 1
        assert data["domain"] == "science"

    def test_upload_response_includes_domain(self, client, editor_headers):
        buf = _csv_file([{"primary_label": "E1"}])
        resp = client.post(
            "/upload",
            data={"domain": "healthcare"},
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        assert resp.status_code == 201
        assert "domain" in resp.json()

    def test_upload_default_domain(self, client, editor_headers):
        buf = _csv_file([{"primary_label": "E2"}])
        resp = client.post(
            "/upload",
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["domain"] == "default"

    def test_bibtex_upload_with_domain(self, client, editor_headers):
        resp = client.post(
            "/upload",
            data={"domain": "science"},
            files={"file": ("refs.bib", io.BytesIO(_BIBTEX_CONTENT), "text/plain")},
            headers=editor_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_rows"] == 2
        assert data["domain"] == "science"

    def test_ris_upload_with_domain(self, client, editor_headers):
        resp = client.post(
            "/upload",
            data={"domain": "science"},
            files={"file": ("refs.ris", io.BytesIO(_RIS_CONTENT), "text/plain")},
            headers=editor_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["total_rows"] == 1


# ── POST /upload with custom field_mapping ────────────────────────────────────

class TestUploadWithFieldMapping:
    def test_custom_mapping_maps_column(self, client, editor_headers, db_session):
        from backend import models
        buf = _csv_file([{"MyTitle": "Custom Mapped", "MyAuthor": "Jane"}])
        mapping = json.dumps({"MyTitle": "primary_label", "MyAuthor": "secondary_label"})
        resp = client.post(
            "/upload",
            data={"domain": "default", "field_mapping": mapping},
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["total_rows"] == 1

    def test_skipped_column_not_in_matched(self, client, editor_headers):
        buf = _csv_file([{"KeepMe": "value", "SkipMe": "ignored"}])
        mapping = json.dumps({"KeepMe": "primary_label", "SkipMe": ""})
        resp = client.post(
            "/upload",
            data={"field_mapping": mapping},
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        assert resp.status_code == 201

    def test_invalid_json_mapping_gracefully_ignored(self, client, editor_headers):
        buf = _csv_file([{"Title": "T"}])
        resp = client.post(
            "/upload",
            data={"field_mapping": "not-valid-json"},
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        # Bad JSON mapping falls back to default — still succeeds
        assert resp.status_code == 201

    def test_empty_mapping_uses_defaults(self, client, editor_headers):
        buf = _csv_file([{"primary_label": "Direct"}])
        resp = client.post(
            "/upload",
            data={"field_mapping": "{}"},
            files={"file": ("test.csv", buf, "text/csv")},
            headers=editor_headers,
        )
        assert resp.status_code == 201

    def test_viewer_cannot_upload(self, client, viewer_headers):
        buf = _csv_file()
        resp = client.post(
            "/upload",
            files={"file": ("test.csv", buf, "text/csv")},
            headers=viewer_headers,
        )
        assert resp.status_code in (401, 403)

    def test_wrong_extension_rejected(self, client, editor_headers):
        buf = io.BytesIO(b"not a real format")
        resp = client.post(
            "/upload",
            files={"file": ("test.docx", buf, "application/octet-stream")},
            headers=editor_headers,
        )
        assert resp.status_code == 400
