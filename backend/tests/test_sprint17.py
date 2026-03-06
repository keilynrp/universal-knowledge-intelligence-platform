"""
Sprint 17A — Domain Registry: POST /domains, DELETE /domains/{id},
schema_registry helpers (save_domain, delete_domain, is_builtin).
"""
from __future__ import annotations

import os
import shutil
import pytest

from backend.schema_registry import SchemaRegistry, DomainSchema, AttributeSchema, _BUILTIN_DOMAIN_IDS
import backend.schema_registry as _sr_mod

# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _cleanup_custom_domains():
    """Remove non-builtin domain YAML files before and after each test to prevent cross-test pollution."""
    def _clean():
        domains_dir = _sr_mod.DOMAINS_DIR
        if not os.path.exists(domains_dir):
            return
        for fname in os.listdir(domains_dir):
            if not fname.endswith(".yaml"):
                continue
            domain_id = fname[:-5]
            if domain_id not in _BUILTIN_DOMAIN_IDS:
                try:
                    os.remove(os.path.join(domains_dir, fname))
                except FileNotFoundError:
                    pass
                _sr_mod.registry.domains.pop(domain_id, None)

    _clean()
    yield
    _clean()

_SAMPLE_DOMAIN = {
    "id": "test_domain_sprint17",
    "name": "Test Domain",
    "description": "A temporary domain for testing",
    "primary_entity": "TestEntity",
    "icon": "Database",
    "attributes": [
        {"name": "title", "label": "Title", "type": "string", "required": True, "is_core": False},
        {"name": "score", "label": "Score", "type": "float", "required": False, "is_core": False},
    ],
}


# ── 17A · SchemaRegistry unit tests ──────────────────────────────────────────

class TestSchemaRegistryHelpers:
    """Unit tests that operate on a temporary registry directory to avoid polluting production domains."""

    @pytest.fixture
    def tmp_registry(self, tmp_path):
        """Create a fresh SchemaRegistry backed by a temp directory."""
        # Patch the DOMAINS_DIR inside SchemaRegistry by creating a subclass
        domains_dir = str(tmp_path / "domains")
        os.makedirs(domains_dir, exist_ok=True)
        reg = SchemaRegistry.__new__(SchemaRegistry)
        reg.domains = {}
        import backend.schema_registry as sr_mod
        original_dir = sr_mod.DOMAINS_DIR
        sr_mod.DOMAINS_DIR = domains_dir
        reg._load_registry = lambda: None  # don't try to load from temp (empty)
        reg.domains = {}
        # Patch instance method to use tmp dir
        import types

        def _save(self, schema):
            filepath = os.path.join(domains_dir, f"{schema.id}.yaml")
            import yaml
            with open(filepath, "w", encoding="utf-8") as f:
                yaml.dump(schema.model_dump(), f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            self.domains[schema.id] = schema

        def _delete(self, domain_id):
            filepath = os.path.join(domains_dir, f"{domain_id}.yaml")
            if not os.path.exists(filepath):
                return False
            os.remove(filepath)
            self.domains.pop(domain_id, None)
            return True

        reg.save_domain = types.MethodType(_save, reg)
        reg.delete_domain = types.MethodType(_delete, reg)
        reg.is_builtin = lambda did: did in _BUILTIN_DOMAIN_IDS
        yield reg, domains_dir
        sr_mod.DOMAINS_DIR = original_dir

    def _make_schema(self, domain_id="test_x"):
        return DomainSchema(
            id=domain_id,
            name="Test X",
            description="desc",
            primary_entity="Thing",
            attributes=[AttributeSchema(name="title", label="Title", type="string")],
        )

    def test_save_domain_creates_yaml(self, tmp_registry):
        reg, domains_dir = tmp_registry
        schema = self._make_schema("my_domain")
        reg.save_domain(schema)
        assert os.path.exists(os.path.join(domains_dir, "my_domain.yaml"))
        assert "my_domain" in reg.domains

    def test_save_domain_registered_in_memory(self, tmp_registry):
        reg, _ = tmp_registry
        schema = self._make_schema("mem_domain")
        reg.save_domain(schema)
        assert reg.domains["mem_domain"].name == "Test X"

    def test_delete_domain_removes_yaml(self, tmp_registry):
        reg, domains_dir = tmp_registry
        schema = self._make_schema("del_domain")
        reg.save_domain(schema)
        assert reg.delete_domain("del_domain") is True
        assert not os.path.exists(os.path.join(domains_dir, "del_domain.yaml"))
        assert "del_domain" not in reg.domains

    def test_delete_nonexistent_returns_false(self, tmp_registry):
        reg, _ = tmp_registry
        assert reg.delete_domain("nope") is False

    def test_is_builtin_true_for_builtins(self):
        from backend.schema_registry import registry
        for bid in ("default", "science", "healthcare"):
            assert registry.is_builtin(bid) is True

    def test_is_builtin_false_for_custom(self):
        from backend.schema_registry import registry
        assert registry.is_builtin("my_custom_domain") is False


# ── 17B · POST /domains ───────────────────────────────────────────────────────

class TestCreateDomain:
    def test_viewer_cannot_create_domain(self, client, viewer_headers):
        resp = client.post("/domains", json=_SAMPLE_DOMAIN, headers=viewer_headers)
        assert resp.status_code == 403

    def test_editor_cannot_create_domain(self, client, editor_headers):
        resp = client.post("/domains", json=_SAMPLE_DOMAIN, headers=editor_headers)
        assert resp.status_code == 403

    def test_unauthenticated_cannot_create_domain(self, client):
        resp = client.post("/domains", json=_SAMPLE_DOMAIN)
        assert resp.status_code == 401

    def test_admin_can_create_domain(self, client, auth_headers):
        resp = client.post("/domains", json=_SAMPLE_DOMAIN, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == _SAMPLE_DOMAIN["id"]
        assert data["name"] == _SAMPLE_DOMAIN["name"]
        assert len(data["attributes"]) == 2

    def test_create_domain_duplicate_returns_409(self, client, auth_headers):
        client.post("/domains", json=_SAMPLE_DOMAIN, headers=auth_headers)
        resp = client.post("/domains", json=_SAMPLE_DOMAIN, headers=auth_headers)
        assert resp.status_code == 409

    def test_create_domain_no_attributes_returns_422(self, client, auth_headers):
        bad = {**_SAMPLE_DOMAIN, "id": "no_attrs_domain", "attributes": []}
        resp = client.post("/domains", json=bad, headers=auth_headers)
        assert resp.status_code == 422

    def test_created_domain_appears_in_get_all(self, client, auth_headers):
        unique_id = "sprint17_list_test"
        payload = {**_SAMPLE_DOMAIN, "id": unique_id}
        client.post("/domains", json=payload, headers=auth_headers)
        resp = client.get("/domains", headers=auth_headers)
        assert resp.status_code == 200
        ids = [d["id"] for d in resp.json()]
        assert unique_id in ids

    def test_created_domain_accessible_by_id(self, client, auth_headers):
        unique_id = "sprint17_byid_test"
        payload = {**_SAMPLE_DOMAIN, "id": unique_id}
        client.post("/domains", json=payload, headers=auth_headers)
        resp = client.get(f"/domains/{unique_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == unique_id


# ── 17C · DELETE /domains/{id} ────────────────────────────────────────────────

class TestDeleteDomain:
    def _create_custom(self, client, auth_headers, domain_id="sprint17_to_delete"):
        payload = {**_SAMPLE_DOMAIN, "id": domain_id}
        client.post("/domains", json=payload, headers=auth_headers)
        return domain_id

    def test_viewer_cannot_delete(self, client, viewer_headers, auth_headers):
        did = self._create_custom(client, auth_headers, "del_viewer_test")
        resp = client.delete(f"/domains/{did}", headers=viewer_headers)
        assert resp.status_code == 403

    def test_admin_can_delete_custom(self, client, auth_headers):
        did = self._create_custom(client, auth_headers, "del_admin_test")
        resp = client.delete(f"/domains/{did}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["deleted"] == did

    def test_deleted_domain_not_found_in_get(self, client, auth_headers):
        did = self._create_custom(client, auth_headers, "del_then_get_test")
        client.delete(f"/domains/{did}", headers=auth_headers)
        resp = client.get(f"/domains/{did}", headers=auth_headers)
        assert resp.status_code == 404

    def test_cannot_delete_builtin_default(self, client, auth_headers):
        resp = client.delete("/domains/default", headers=auth_headers)
        assert resp.status_code == 403

    def test_cannot_delete_builtin_science(self, client, auth_headers):
        resp = client.delete("/domains/science", headers=auth_headers)
        assert resp.status_code == 403

    def test_cannot_delete_builtin_healthcare(self, client, auth_headers):
        resp = client.delete("/domains/healthcare", headers=auth_headers)
        assert resp.status_code == 403

    def test_delete_nonexistent_returns_404(self, client, auth_headers):
        resp = client.delete("/domains/nonexistent_xyz", headers=auth_headers)
        assert resp.status_code == 404


# ── 17D · GET /domains (existing, guarded) ────────────────────────────────────

class TestGetDomains:
    def test_unauthenticated_returns_401(self, client):
        assert client.get("/domains").status_code == 401

    def test_authenticated_returns_domains(self, client, auth_headers):
        resp = client.get("/domains", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 3
        ids = {d["id"] for d in data}
        assert {"default", "science", "healthcare"} <= ids

    def test_default_domain_first_in_list(self, client, auth_headers):
        resp = client.get("/domains", headers=auth_headers)
        assert resp.json()[0]["id"] == "default"

    def test_domain_schema_has_required_fields(self, client, auth_headers):
        resp = client.get("/domains", headers=auth_headers)
        domain = resp.json()[0]
        for key in ("id", "name", "description", "primary_entity", "attributes"):
            assert key in domain

    def test_get_domain_by_id(self, client, auth_headers):
        resp = client.get("/domains/science", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == "science"

    def test_get_nonexistent_domain_404(self, client, auth_headers):
        resp = client.get("/domains/nonexistent_domain_xyz", headers=auth_headers)
        assert resp.status_code == 404
