def test_assistant_actions_list_marks_editor_executable(client, editor_headers, monkeypatch, tmp_path):
    monkeypatch.setenv("ASSISTANT_ACTION_GUARDRAILS_PATH", str(tmp_path / "guardrails.json"))

    resp = client.get("/assistant/actions", headers=editor_headers)

    assert resp.status_code == 200
    items = {item["id"]: item for item in resp.json()["items"]}
    assert items["entity-enrich-current"]["executable"] is True
    assert items["rag-reindex"]["executable"] is False


def test_admin_can_update_assistant_guardrail(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setenv("ASSISTANT_ACTION_GUARDRAILS_PATH", str(tmp_path / "guardrails.json"))

    resp = client.put(
        "/assistant/actions/entity-enrich-current",
        headers=auth_headers,
        json={"enabled": False, "allowed_roles": ["super_admin", "admin"], "requires_confirmation": True},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False
    assert data["allowed_roles"] == ["super_admin", "admin"]
    assert data["configured"] is True


def test_editor_blocked_when_entity_enrich_guardrail_disabled(client, auth_headers, editor_headers, monkeypatch, tmp_path):
    monkeypatch.setenv("ASSISTANT_ACTION_GUARDRAILS_PATH", str(tmp_path / "guardrails.json"))
    client.put(
        "/assistant/actions/entity-enrich-current",
        headers=auth_headers,
        json={"enabled": False},
    )

    resp = client.post("/enrich/row/999999", headers=editor_headers)

    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"]


def test_viewer_cannot_be_added_to_high_risk_action(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setenv("ASSISTANT_ACTION_GUARDRAILS_PATH", str(tmp_path / "guardrails.json"))

    resp = client.put(
        "/assistant/actions/rag-reindex",
        headers=auth_headers,
        json={"allowed_roles": ["super_admin", "viewer"]},
    )

    assert resp.status_code == 400
