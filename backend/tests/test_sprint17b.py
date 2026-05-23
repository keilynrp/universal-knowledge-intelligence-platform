"""
Sprint 17B — OLAP Cube Explorer: /cube/dimensions, POST /cube/query, GET /cube/export.
"""
from __future__ import annotations

import pytest


# ── 17E · GET /cube/dimensions/{domain_id} ────────────────────────────────────

class TestCubeDimensions:
    def test_unauthenticated_returns_401(self, client):
        assert client.get("/cube/dimensions/default").status_code == 401

    def test_authenticated_returns_dimensions(self, client, auth_headers):
        resp = client.get("/cube/dimensions/default", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_dimensions_have_required_fields(self, client, auth_headers):
        resp = client.get("/cube/dimensions/default", headers=auth_headers)
        assert resp.status_code == 200
        dims = resp.json()
        if dims:  # may be empty if no data loaded, but shape must be correct
            for dim in dims:
                assert "name" in dim
                assert "label" in dim
                assert "type" in dim
                assert "distinct_count" in dim

    def test_nonexistent_domain_returns_404(self, client, auth_headers):
        resp = client.get("/cube/dimensions/nonexistent_xyz", headers=auth_headers)
        assert resp.status_code == 404

    def test_viewer_can_access(self, client, viewer_headers):
        resp = client.get("/cube/dimensions/default", headers=viewer_headers)
        assert resp.status_code == 200

    def test_science_domain_dimensions(self, client, auth_headers):
        resp = client.get("/cube/dimensions/science", headers=auth_headers)
        assert resp.status_code == 200
        dims = resp.json()
        names = [d["name"] for d in dims]
        # Science domain should expose these attributes (minus skipped ones like doi, title)
        assert any(n in names for n in ("journal", "year", "citations", "authors"))

    def test_science_domain_defaults_stay_scientific(self, client, auth_headers):
        resp = client.get("/cube/dimensions/science", headers=auth_headers)
        assert resp.status_code == 200
        names = {d["name"] for d in resp.json()}

        assert {"authors", "journal", "year", "citations", "institution"} <= names
        assert {"sku", "gtin", "barcode", "brand"}.isdisjoint(names)


# ── 17F · POST /cube/query ────────────────────────────────────────────────────

class TestCubeQuery:
    def _payload(self, **kwargs):
        defaults = {"domain_id": "default", "group_by": ["validation_status"], "filters": {}}
        defaults.update(kwargs)
        return defaults

    def test_unauthenticated_returns_401(self, client):
        resp = client.post("/cube/query", json=self._payload())
        assert resp.status_code == 401

    def test_valid_query_returns_200(self, client, auth_headers):
        resp = client.post("/cube/query", json=self._payload(), headers=auth_headers)
        assert resp.status_code == 200

    def test_response_shape(self, client, auth_headers):
        resp = client.post("/cube/query", json=self._payload(), headers=auth_headers)
        data = resp.json()
        for key in ("domain_id", "group_by", "filters", "total", "rows"):
            assert key in data

    def test_rows_have_values_count_pct(self, client, auth_headers):
        resp = client.post("/cube/query", json=self._payload(), headers=auth_headers)
        data = resp.json()
        for row in data["rows"]:
            assert "values" in row
            assert "count" in row
            assert "pct" in row

    def test_single_group_by_dimension(self, client, auth_headers):
        resp = client.post("/cube/query", json=self._payload(group_by=["entity_type"]), headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["group_by"] == ["entity_type"]

    def test_two_group_by_dimensions_cross_tab(self, client, auth_headers):
        resp = client.post("/cube/query", json=self._payload(group_by=["validation_status", "entity_type"]), headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["group_by"]) == 2

    def test_invalid_group_by_returns_422(self, client, auth_headers):
        # Unknown dimension not in domain schema
        resp = client.post("/cube/query", json=self._payload(group_by=["nonexistent_field_xyz"]), headers=auth_headers)
        assert resp.status_code == 422

    def test_three_dimensions_returns_422(self, client, auth_headers):
        # group_by max length is 2
        resp = client.post("/cube/query", json=self._payload(group_by=["validation_status", "entity_type", "domain"]), headers=auth_headers)
        assert resp.status_code == 422

    def test_nonexistent_domain_returns_422(self, client, auth_headers):
        resp = client.post("/cube/query", json=self._payload(domain_id="nonexistent_xyz"), headers=auth_headers)
        assert resp.status_code == 422

    def test_filter_applied_reduces_results(self, client, auth_headers, db_session):
        """With a filter that matches nothing the total should be 0."""
        resp = client.post("/cube/query", json=self._payload(
            filters={"validation_status": "__no_such_value_ever__"}
        ), headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["rows"] == []

    def test_viewer_can_query(self, client, viewer_headers):
        resp = client.post("/cube/query", json=self._payload(), headers=viewer_headers)
        assert resp.status_code == 200

    def test_pct_sums_to_approximately_100(self, client, auth_headers, db_session):
        """Sum of pct values should be ≈100 if there are rows."""
        from backend import models
        db_session.add(models.RawEntity(primary_label="A", validation_status="active"))
        db_session.add(models.RawEntity(primary_label="B", validation_status="inactive"))
        db_session.commit()

        resp = client.post("/cube/query", json=self._payload(group_by=["validation_status"]), headers=auth_headers)
        data = resp.json()
        if data["rows"]:
            total_pct = sum(r["pct"] for r in data["rows"])
            assert abs(total_pct - 100.0) < 1.0  # allow rounding


# ── 17G · GET /cube/export/{domain_id} ───────────────────────────────────────

class TestCubeExport:
    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/cube/export/default?dimension=validation_status")
        assert resp.status_code == 401

    def test_export_returns_xlsx(self, client, auth_headers):
        resp = client.get("/cube/export/default?dimension=validation_status", headers=auth_headers)
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers.get("content-type", "")

    def test_export_content_disposition_header(self, client, auth_headers):
        resp = client.get("/cube/export/default?dimension=validation_status", headers=auth_headers)
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert ".xlsx" in cd

    def test_export_nonexistent_domain_returns_422(self, client, auth_headers):
        resp = client.get("/cube/export/nonexistent_xyz?dimension=validation_status", headers=auth_headers)
        assert resp.status_code == 422

    def test_export_unsafe_dimension_returns_422(self, client, auth_headers):
        resp = client.get("/cube/export/default?dimension=validation_status%3BDROP%20TABLE", headers=auth_headers)
        assert resp.status_code == 422

    def test_export_missing_dimension_param_returns_422(self, client, auth_headers):
        resp = client.get("/cube/export/default", headers=auth_headers)
        assert resp.status_code == 422

    def test_viewer_can_export(self, client, viewer_headers):
        resp = client.get("/cube/export/default?dimension=validation_status", headers=viewer_headers)
        assert resp.status_code == 200
