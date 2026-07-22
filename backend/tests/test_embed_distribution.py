"""
Embed widget distribution contract — the part a customer copies and pastes.

Spec: openspec/changes/fix-embed-widget-distribution/specs/embed-widget-distribution/spec.md
  - "Embed snippets are usable without hand-editing"
  - "The iframe snippet targets the rendering page"
  - "The JS snippet renders presentable output"

All three defects under test here shipped in Sprint 93 with zero coverage:
the iframe pointed at a route that never existed, both snippets hardcoded
localhost, and the JS snippet rendered a raw JSON dump.
"""
from __future__ import annotations

import re

import pytest

PUBLIC_API = "https://api.ukip.example.com"
PUBLIC_APP = "https://ukip.example.com"


@pytest.fixture()
def public_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UKIP_PUBLIC_API_URL", PUBLIC_API)
    monkeypatch.setenv("FRONTEND_URL", PUBLIC_APP)


@pytest.fixture()
def widget_token(client, auth_headers) -> str:
    response = client.post(
        "/widgets",
        json={"name": "Dist Test", "widget_type": "entity_stats", "config": {}},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["public_token"]


def _snippet(client, token: str) -> dict:
    response = client.get(f"/embed/{token}/snippet")
    assert response.status_code == 200, response.text
    return response.json()


# ── Usable without hand-editing ───────────────────────────────────────────────

class TestNoHandEditing:
    def test_snippets_carry_no_localhost(self, client, widget_token, public_urls):
        data = _snippet(client, widget_token)
        combined = data["iframe_snippet"] + data["js_snippet"]
        assert "localhost" not in combined
        assert "127.0.0.1" not in combined

    def test_js_snippet_uses_configured_api_base(
        self, client, widget_token, public_urls
    ):
        data = _snippet(client, widget_token)
        assert f"{PUBLIC_API}/embed/{widget_token}/data" in data["js_snippet"]

    def test_api_base_falls_back_to_request_origin(
        self, client, widget_token, monkeypatch
    ):
        """Unset env must yield the origin the request arrived on — 'probably
        right' — never a hardcoded dev host — 'definitely wrong'."""
        monkeypatch.delenv("UKIP_PUBLIC_API_URL", raising=False)
        data = _snippet(client, widget_token)
        assert "http://testserver/embed/" in data["js_snippet"]
        assert "localhost:8000" not in data["js_snippet"]

    def test_trailing_slashes_do_not_double(
        self, client, widget_token, monkeypatch
    ):
        monkeypatch.setenv("UKIP_PUBLIC_API_URL", PUBLIC_API + "/")
        monkeypatch.setenv("FRONTEND_URL", PUBLIC_APP + "/")
        data = _snippet(client, widget_token)
        combined = data["iframe_snippet"] + data["js_snippet"]
        assert "//embed" not in combined.replace("://", "")


# ── Iframe targets the rendering page ─────────────────────────────────────────

class TestIframeTarget:
    def test_iframe_points_at_frontend_embed_route(
        self, client, widget_token, public_urls
    ):
        data = _snippet(client, widget_token)
        assert f'src="{PUBLIC_APP}/embed/{widget_token}"' in data["iframe_snippet"]

    def test_no_frame_path_anywhere(self, client, widget_token, public_urls):
        """/embed/{token}/frame never existed; nothing may reference it."""
        data = _snippet(client, widget_token)
        assert "/frame" not in data["iframe_snippet"] + data["js_snippet"]

    def test_iframe_has_a_title_for_accessibility(
        self, client, widget_token, public_urls
    ):
        data = _snippet(client, widget_token)
        assert 'title="' in data["iframe_snippet"]


# ── JS snippet renders, not dumps ─────────────────────────────────────────────

class TestJsSnippetRendering:
    def test_no_raw_json_dump(self, client, widget_token, public_urls):
        js = _snippet(client, widget_token)["js_snippet"]
        assert "JSON.stringify" not in js
        assert "<pre>" not in js

    def test_dependency_free(self, client, widget_token, public_urls):
        """No external script/style: the snippet must work on any page as-is."""
        js = _snippet(client, widget_token)["js_snippet"]
        assert not re.search(r'<script[^>]+src\s*=', js)
        assert "<link" not in js
        assert "@import" not in js

    def test_renders_labelled_values(self, client, widget_token, public_urls):
        """The renderer must reference real payload fields, not echo the blob."""
        js = _snippet(client, widget_token)["js_snippet"]
        assert "textContent" in js or "innerText" in js


# ── Config endpoint exposes what the frontend needs ───────────────────────────

class TestConfigExposesAllowedOrigins:
    def test_config_includes_allowed_origins(self, client, auth_headers):
        """The embed page needs allowed_origins to emit its frame-ancestors
        header; the public config endpoint is where it can get them."""
        created = client.post(
            "/widgets",
            json={
                "name": "Origins Test",
                "widget_type": "entity_stats",
                "config": {},
                "allowed_origins": "https://cliente.example.com",
            },
            headers=auth_headers,
        ).json()
        response = client.get(f"/embed/{created['public_token']}/config")
        assert response.status_code == 200
        assert response.json()["allowed_origins"] == "https://cliente.example.com"
