"""
Sprint 49 — Tool Registry
GET  /context/tools
POST /context/invoke
"""
import pytest

_EXPECTED_TOOLS = {
    "get_entity_stats",
    "get_gaps",
    "get_topics",
    "get_harmonization_log",
    "get_enrichment_stats",
    "analyze_domain",
    "find_researchers_by_topic",
    "get_topic_researcher_graph",
}


def test_list_tools_requires_auth(client):
    resp = client.get("/context/tools")
    assert resp.status_code in (401, 403)


def test_list_tools_returns_all_builtin(client, auth_headers):
    resp = client.get("/context/tools", headers=auth_headers)
    assert resp.status_code == 200
    tools = resp.json()
    names = {t["name"] for t in tools}
    assert _EXPECTED_TOOLS == names


def test_tool_has_schema(client, auth_headers):
    resp = client.get("/context/tools", headers=auth_headers)
    tools = {t["name"]: t for t in resp.json()}
    for name in _EXPECTED_TOOLS:
        assert "description" in tools[name]
        assert "parameters" in tools[name]


def test_invoke_entity_stats(client, editor_headers, db_session):
    resp = client.post(
        "/context/invoke",
        json={"tool": "get_entity_stats", "params": {"domain_id": "default"}},
        headers=editor_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool"] == "get_entity_stats"
    result = data["result"]
    assert "total" in result
    assert "pct_enriched" in result


def test_invoke_unknown_tool_404(client, editor_headers):
    resp = client.post(
        "/context/invoke",
        json={"tool": "not_a_real_tool"},
        headers=editor_headers,
    )
    assert resp.status_code == 404


def test_viewer_cannot_invoke(client, viewer_headers):
    resp = client.post(
        "/context/invoke",
        json={"tool": "get_entity_stats", "params": {}},
        headers=viewer_headers,
    )
    assert resp.status_code in (401, 403)
