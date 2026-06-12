from fastapi.testclient import TestClient

from backend.enterprise_controls import ENTERPRISE_CONTROLS


def test_enterprise_readiness_returns_control_program(client: TestClient, auth_headers: dict):
    response = client.get("/ops/enterprise-readiness", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "enterprise_readiness_program"
    assert body["target_claim"] == "regulated_institutional_enterprise_ready"
    assert body["summary"]["total_controls"] == len(ENTERPRISE_CONTROLS)
    assert {item["control_id"] for item in body["controls"]} == {
        control.control_id for control in ENTERPRISE_CONTROLS
    }


def test_enterprise_controls_expose_next_gate_and_evidence(client: TestClient, auth_headers: dict):
    body = client.get("/ops/enterprise-readiness", headers=auth_headers).json()
    for control in body["controls"]:
        assert control["owner"]
        assert control["next_gate"]
        assert "related_work" in control
        assert control["current_maturity"]
        assert control["target_maturity"]


def test_enterprise_readiness_includes_non_certification_disclaimer(client: TestClient, auth_headers: dict):
    body = client.get("/ops/enterprise-readiness", headers=auth_headers).json()
    assert "does not assert certification" in body["claim_disclaimer"]


def test_enterprise_readiness_requires_admin(client: TestClient, viewer_headers: dict):
    response = client.get("/ops/enterprise-readiness", headers=viewer_headers)
    assert response.status_code == 403
