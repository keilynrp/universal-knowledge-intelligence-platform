"""Tests for engine status endpoints."""
import pytest


class TestEngineHealth:
    def test_engine_health_no_engine(self, client, auth_headers):
        """When engine is not configured, returns disabled status."""
        resp = client.get("/engine/health", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["engine_available"] is False

    def test_engine_job_not_found(self, client, auth_headers):
        """When engine is not configured, job lookup returns 404."""
        resp = client.get("/engine/jobs/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    def test_engine_health_requires_auth(self, client):
        """Engine health endpoint requires authentication."""
        resp = client.get("/engine/health")
        assert resp.status_code in (401, 403)
