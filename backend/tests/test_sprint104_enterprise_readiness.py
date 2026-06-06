from fastapi.testclient import TestClient


def test_enterprise_readiness_register_returns_prioritized_baseline(client: TestClient, auth_headers: dict):
    response = client.get("/ops/enterprise-readiness", headers=auth_headers)
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "baseline"
    assert body["focus_mvp"] == "research_intelligence"
    assert body["summary"]["total_gaps"] == len(body["gaps"])
    # EPIC-017 closed the last open P0 (secrets_rotation) — zero open P0 gaps remain.
    assert body["summary"]["priority_counts"]["P0"] == 0

    priorities = [gap["priority"] for gap in body["gaps"]]
    assert priorities == sorted(priorities, key=lambda value: {"P0": 0, "P1": 1, "P2": 2}[value])


def test_enterprise_readiness_gaps_include_impact_and_recommendation(client: TestClient, auth_headers: dict):
    response = client.get("/ops/enterprise-readiness", headers=auth_headers)
    assert response.status_code == 200

    for gap in response.json()["gaps"]:
        assert gap["impact"]
        assert gap["recommendation"]
        assert gap["related_work"]


def test_enterprise_readiness_roadmap_hooks_reference_follow_up_work(client: TestClient, auth_headers: dict):
    response = client.get("/ops/enterprise-readiness", headers=auth_headers)
    assert response.status_code == 200

    hooks = response.json()["roadmap_hooks"]
    hook_ids = {hook["id"] for hook in hooks}
    # EPIC-012 is now resolved, so the hooks should point at the remaining work.
    assert "EPIC-012" not in hook_ids
    assert "US-042" in hook_ids
    # EPIC-017 resolved secrets rotation — its roadmap hook is gone.
    assert "COMPLIANCE-TBD-SECRETS" not in hook_ids


def test_enterprise_readiness_reports_resolved_tenant_isolation(client: TestClient, auth_headers: dict):
    response = client.get("/ops/enterprise-readiness", headers=auth_headers)
    assert response.status_code == 200

    body = response.json()
    resolved = body.get("resolved", [])
    assert body["summary"]["resolved_count"] == len(resolved)

    resolved_ids = {item["id"] for item in resolved}
    assert "tenant_isolation" in resolved_ids

    tenant = next(item for item in resolved if item["id"] == "tenant_isolation")
    assert tenant["status"] == "resolved"
    assert tenant["evidence"]
    # Resolved items must not also appear as open gaps.
    open_ids = {gap["id"] for gap in body["gaps"]}
    assert "tenant_isolation" not in open_ids


def test_enterprise_readiness_reports_resolved_secrets_rotation(client: TestClient, auth_headers: dict):
    response = client.get("/ops/enterprise-readiness", headers=auth_headers)
    assert response.status_code == 200

    body = response.json()
    resolved = body.get("resolved", [])
    resolved_ids = {item["id"] for item in resolved}
    assert "secrets_rotation" in resolved_ids

    secrets = next(item for item in resolved if item["id"] == "secrets_rotation")
    assert secrets["status"] == "resolved"
    assert secrets["priority"] == "P0"
    assert secrets["evidence"]
    # Resolved items must not also appear as open gaps.
    open_ids = {gap["id"] for gap in body["gaps"]}
    assert "secrets_rotation" not in open_ids


def test_enterprise_readiness_requires_admin(client: TestClient, viewer_headers: dict):
    response = client.get("/ops/enterprise-readiness", headers=viewer_headers)
    assert response.status_code == 403
