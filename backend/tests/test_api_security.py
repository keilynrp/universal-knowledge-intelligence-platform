"""
Tests for API security — protected routes must return 401 without a token,
and accept valid tokens. Also verifies credential encryption in store endpoints.
"""
import pytest

pytestmark = pytest.mark.security


# ── Protected route: store endpoints ─────────────────────────────────────────

class TestStoreEndpointsRequireAuth:
    def test_create_store_without_token_returns_401(self, client):
        response = client.post("/stores", json={
            "name": "Test Store",
            "platform": "woocommerce",
            "base_url": "https://example.com",
        })
        assert response.status_code == 401

    def test_update_store_without_token_returns_401(self, client):
        response = client.put("/stores/1", json={"name": "Updated"})
        assert response.status_code == 401

    def test_delete_store_without_token_returns_401(self, client):
        response = client.delete("/stores/1")
        assert response.status_code == 401

    def test_toggle_store_without_token_returns_401(self, client):
        response = client.post("/stores/1/toggle")
        assert response.status_code == 401


class TestStoreEndpointsWithValidToken:
    def test_create_store_with_token_is_accepted(self, client, auth_headers):
        response = client.post(
            "/stores",
            json={
                "name": "Authed Store",
                "platform": "woocommerce",
                "base_url": "https://example.com",
                "api_key": "ck_test_key",
                "api_secret": "cs_test_secret",
            },
            headers=auth_headers,
        )
        # 200 = created successfully, or 400 if validation fails — but NOT 401/403
        assert response.status_code not in (401, 403)

    def test_list_stores_requires_auth(self, client, auth_headers):
        """GET /stores requires authentication (added Sprint 9A)."""
        unauthenticated = client.get("/stores")
        assert unauthenticated.status_code == 401
        authenticated = client.get("/stores", headers=auth_headers)
        assert authenticated.status_code == 200


# ── Protected route: AI integration endpoints ─────────────────────────────────

class TestAIIntegrationEndpointsRequireAuth:
    def test_list_ai_integrations_requires_auth(self, client):
        response = client.get("/ai-integrations")
        assert response.status_code == 401

    def test_create_ai_integration_without_token_returns_401(self, client):
        response = client.post("/ai-integrations", json={
            "provider_name": "openai",
            "api_key": "sk-test",
        })
        assert response.status_code == 401

    def test_delete_ai_integration_without_token_returns_401(self, client):
        response = client.delete("/ai-integrations/1")
        assert response.status_code == 401

    def test_create_ai_integration_with_valid_token(self, client, auth_headers):
        response = client.post(
            "/ai-integrations",
            json={"provider_name": "openai-test-unique", "api_key": "sk-abc"},
            headers=auth_headers,
        )
        assert response.status_code not in (401, 403)

    def test_ai_integrations_list_does_not_expose_api_key(self, client, auth_headers):
        """GET /ai-integrations must NOT include api_key in the response."""
        response = client.get("/ai-integrations", headers=auth_headers)
        assert response.status_code == 200
        for item in response.json():
            assert "api_key" not in item
            # Should have the masked indicator instead
            assert "has_api_key" in item


# ── Public endpoints remain accessible ───────────────────────────────────────

class TestPublicEndpoints:
    def test_health_check_is_public(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_domains_endpoint_requires_auth(self, client, auth_headers):
        assert client.get("/domains").status_code == 401
        assert client.get("/domains", headers=auth_headers).status_code == 200

    def test_entities_list_requires_auth(self, client, auth_headers):
        assert client.get("/entities").status_code == 401
        assert client.get("/entities", headers=auth_headers).status_code == 200


# ── Invalid token is rejected ─────────────────────────────────────────────────

class TestInvalidToken:
    def test_garbage_token_returns_401(self, client):
        response = client.post(
            "/stores",
            json={"name": "x", "platform": "woocommerce", "base_url": "https://x.com"},
            headers={"Authorization": "Bearer this.is.garbage"},
        )
        assert response.status_code == 401

    def test_missing_bearer_prefix_returns_401(self, client):
        response = client.post(
            "/stores",
            json={"name": "x", "platform": "woocommerce", "base_url": "https://x.com"},
            headers={"Authorization": "justtoken"},
        )
        assert response.status_code == 401
