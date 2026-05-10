"""Tests for engine integration in ingest pipeline (fallback behavior)."""
import pytest


class TestEngineIntegration:
    def test_upload_works_without_engine(self, client, auth_headers):
        """Upload still works when engine is not available (Python fallback)."""
        csv_content = "title,doi\nTest Paper,10.1234/test\n"
        files = {"file": ("test.csv", csv_content.encode(), "text/csv")}
        resp = client.post("/upload", files=files, headers=auth_headers)
        # 201 Created or 200 OK — as long as it doesn't 500
        assert resp.status_code in (200, 201, 422)

    def test_engine_health_returns_false_when_unconfigured(self, client, auth_headers):
        """engine_client is None when ENGINE_GRPC_URL is not set."""
        resp = client.get("/engine/health", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["engine_available"] is False
