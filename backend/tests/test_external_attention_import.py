"""Tests for external attention import endpoints and snippet-enhanced explanations."""
import io
import json

import pytest

from backend import models
from backend.analyzers.external_attention import compute_attention_summary


# ── Unit tests: snippet-enhanced explanations ────────────────────────────────


class TestSnippetExplanations:
    def test_explanation_includes_snippet_from_top_source(self):
        attrs = {
            "external_attention_observations": [
                {
                    "source_type": "news",
                    "mention_count": 5,
                    "last_seen_at": "2026-05-01T00:00:00Z",
                    "title": "Major breakthrough in AI safety",
                    "url": "https://example.com/article1",
                    "snippet": "Researchers announced a new framework...",
                },
                {
                    "source_type": "blog",
                    "mention_count": 1,
                    "last_seen_at": "2026-05-01T00:00:00Z",
                },
            ]
        }

        payload = compute_attention_summary(json.dumps(attrs))

        top_source_expl = next(
            e for e in payload["explanations"] if e["type"] == "top_source"
        )
        assert "snippet" in top_source_expl
        assert top_source_expl["snippet"]["title"] == "Major breakthrough in AI safety"
        assert top_source_expl["snippet"]["url"] == "https://example.com/article1"
        assert top_source_expl["snippet"]["text"] == "Researchers announced a new framework..."

    def test_explanation_no_snippet_when_not_available(self):
        attrs = {
            "external_attention_observations": [
                {"source_type": "news", "mention_count": 5, "last_seen_at": "2026-05-01T00:00:00Z"},
            ]
        }

        payload = compute_attention_summary(json.dumps(attrs))

        top_source_expl = next(
            e for e in payload["explanations"] if e["type"] == "top_source"
        )
        assert "snippet" not in top_source_expl

    def test_policy_explanation_includes_snippet(self):
        attrs = {
            "external_attention_observations": [
                {
                    "source_type": "policy",
                    "mention_count": 3,
                    "last_seen_at": "2026-05-01T00:00:00Z",
                    "title": "EU Regulation on AI Act",
                    "url": "https://eur-lex.europa.eu/ai-act",
                },
                {
                    "source_type": "news",
                    "mention_count": 2,
                    "last_seen_at": "2026-04-15T00:00:00Z",
                },
                {
                    "source_type": "blog",
                    "mention_count": 1,
                    "last_seen_at": "2026-04-10T00:00:00Z",
                },
            ]
        }

        payload = compute_attention_summary(json.dumps(attrs))

        policy_expl = next(
            e for e in payload["explanations"] if e["type"] == "policy_mention"
        )
        assert "snippet" in policy_expl
        assert policy_expl["snippet"]["title"] == "EU Regulation on AI Act"

    def test_spike_explanation_includes_snippet_for_period(self):
        attrs = {
            "external_attention_observations": [
                {"source_type": "social_web", "mention_count": 1, "last_seen_at": "2026-01-10T00:00:00Z"},
                {"source_type": "social_web", "mention_count": 1, "last_seen_at": "2026-02-10T00:00:00Z"},
                {
                    "source_type": "policy",
                    "mention_count": 8,
                    "last_seen_at": "2026-03-10T00:00:00Z",
                    "title": "WHO report on pandemic prep",
                    "url": "https://who.int/report",
                    "snippet": "The organization released...",
                },
            ]
        }

        payload = compute_attention_summary(json.dumps(attrs))

        spike_expl = next(
            e for e in payload["explanations"] if e["type"] == "attention_spike"
        )
        assert "snippet" in spike_expl
        assert spike_expl["snippet"]["title"] == "WHO report on pandemic prep"


# ── Integration tests: import endpoints ──────────────────────────────────────


class TestBulkImportJSON:
    def test_bulk_import_creates_observations(self, client, session_factory, auth_headers):
        with session_factory() as db:
            entity = models.RawEntity(
                domain="science",
                primary_label="Test Entity for Import",
                attributes_json="{}",
            )
            db.add(entity)
            db.commit()
            entity_id = entity.id

        observations = [
            {
                "entity_id": entity_id,
                "source_type": "news",
                "mention_count": 3,
                "last_seen_at": "2026-05-10T00:00:00Z",
                "title": "New discovery",
                "url": "https://news.example.com/1",
                "snippet": "Scientists found...",
            },
            {
                "entity_id": entity_id,
                "source_type": "policy",
                "mention_count": 1,
                "last_seen_at": "2026-05-12T00:00:00Z",
            },
        ]

        resp = client.post(
            "/external-attention/import",
            json=observations,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["imported"] == 2
        assert body["entities_updated"] == 1
        assert body["skipped"] == 0

        # Verify persisted
        with session_factory() as db:
            e = db.query(models.RawEntity).filter_by(id=entity_id).first()
            attrs = json.loads(e.attributes_json)
            obs = attrs["external_attention_observations"]
            assert len(obs) == 2
            assert obs[0]["title"] == "New discovery"
            assert obs[0]["snippet"] == "Scientists found..."

    def test_bulk_import_deduplicates_by_source_and_url(self, client, session_factory, auth_headers):
        with session_factory() as db:
            entity = models.RawEntity(
                domain="science",
                primary_label="Dedup Test Entity",
                attributes_json=json.dumps({
                    "external_attention_observations": [
                        {
                            "source_type": "news",
                            "mention_count": 2,
                            "url": "https://example.com/existing",
                            "title": "Old title",
                        }
                    ]
                }),
            )
            db.add(entity)
            db.commit()
            entity_id = entity.id

        observations = [
            {
                "entity_id": entity_id,
                "source_type": "news",
                "mention_count": 5,
                "last_seen_at": "2026-05-15T00:00:00Z",
                "url": "https://example.com/existing",
                "title": "Updated title",
            },
        ]

        resp = client.post(
            "/external-attention/import",
            json=observations,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        assert resp.json()["imported"] == 1

        # Verify dedup: should still be 1 observation, updated
        with session_factory() as db:
            e = db.query(models.RawEntity).filter_by(id=entity_id).first()
            attrs = json.loads(e.attributes_json)
            obs = attrs["external_attention_observations"]
            assert len(obs) == 1
            assert obs[0]["mention_count"] == 5  # updated to higher value
            assert obs[0]["title"] == "Updated title"

    def test_bulk_import_skips_missing_entities(self, client, auth_headers):
        observations = [
            {"entity_id": 999999, "source_type": "news", "mention_count": 1},
        ]

        resp = client.post(
            "/external-attention/import",
            json=observations,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["imported"] == 0
        assert body["skipped"] == 1
        assert "999999" in body["warnings"][0]

    def test_bulk_import_rejects_oversized_batch(self, client, auth_headers):
        observations = [
            {"entity_id": 1, "source_type": "news", "mention_count": 1}
        ] * 5001

        resp = client.post(
            "/external-attention/import",
            json=observations,
            headers=auth_headers,
        )

        assert resp.status_code == 422

    def test_bulk_import_requires_editor_role(self, client, viewer_headers):
        resp = client.post(
            "/external-attention/import",
            json=[{"entity_id": 1, "source_type": "news", "mention_count": 1}],
            headers=viewer_headers,
        )

        assert resp.status_code == 403


class TestCSVImport:
    def test_csv_import_parses_and_merges(self, client, session_factory, auth_headers):
        with session_factory() as db:
            entity = models.RawEntity(
                domain="science",
                primary_label="CSV Import Entity",
                attributes_json="{}",
            )
            db.add(entity)
            db.commit()
            entity_id = entity.id

        csv_content = (
            "entity_id,source_type,mention_count,last_seen_at,title,url,snippet\n"
            f"{entity_id},news,4,2026-05-10T00:00:00Z,Breaking News,https://news.com/1,Something happened\n"
            f"{entity_id},blog,2,2026-05-11T00:00:00Z,Blog Post,https://blog.com/1,\n"
        )

        resp = client.post(
            "/external-attention/import/csv",
            files={"file": ("attention.csv", io.BytesIO(csv_content.encode()), "text/csv")},
            headers=auth_headers,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["imported"] == 2
        assert body["entities_updated"] == 1

        # Verify
        with session_factory() as db:
            e = db.query(models.RawEntity).filter_by(id=entity_id).first()
            attrs = json.loads(e.attributes_json)
            obs = attrs["external_attention_observations"]
            assert len(obs) == 2
            assert obs[0]["title"] == "Breaking News"

    def test_csv_import_reports_bad_rows(self, client, session_factory, auth_headers):
        csv_content = (
            "entity_id,source_type,mention_count\n"
            ",news,1\n"  # missing entity_id
            "abc,news,1\n"  # invalid entity_id
        )

        resp = client.post(
            "/external-attention/import/csv",
            files={"file": ("bad.csv", io.BytesIO(csv_content.encode()), "text/csv")},
            headers=auth_headers,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["imported"] == 0
        assert len(body["warnings"]) >= 2


class TestSingleEntityImport:
    def test_single_entity_import(self, client, session_factory, auth_headers):
        with session_factory() as db:
            entity = models.RawEntity(
                domain="science",
                primary_label="Single Import Entity",
                attributes_json="{}",
            )
            db.add(entity)
            db.commit()
            entity_id = entity.id

        observations = [
            {
                "source_type": "wikipedia",
                "mention_count": 1,
                "last_seen_at": "2026-05-01T00:00:00Z",
                "title": "Wikipedia article",
                "url": "https://en.wikipedia.org/wiki/Test",
            },
            {
                "source_type": "repository",
                "mention_count": 3,
                "title": "GitHub repo",
                "url": "https://github.com/test/repo",
                "snippet": "A popular library for...",
            },
        ]

        resp = client.post(
            f"/entities/{entity_id}/external-attention/import",
            json=observations,
            headers=auth_headers,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["imported"] == 2
        assert body["total_observations"] == 2

    def test_single_entity_import_404_for_missing_entity(self, client, auth_headers):
        resp = client.post(
            "/entities/999999/external-attention/import",
            json=[{"source_type": "news", "mention_count": 1}],
            headers=auth_headers,
        )

        assert resp.status_code == 404

    def test_single_entity_attention_score_updates_after_import(
        self, client, session_factory, auth_headers
    ):
        with session_factory() as db:
            entity = models.RawEntity(
                domain="science",
                primary_label="Attention Score Test",
                attributes_json="{}",
            )
            db.add(entity)
            db.commit()
            entity_id = entity.id

        # Import observations
        observations = [
            {"source_type": "policy", "mention_count": 5, "last_seen_at": "2026-05-01T00:00:00Z"},
            {"source_type": "news", "mention_count": 10, "last_seen_at": "2026-05-10T00:00:00Z"},
        ]
        resp = client.post(
            f"/entities/{entity_id}/external-attention/import",
            json=observations,
            headers=auth_headers,
        )
        assert resp.status_code == 201

        # Verify attention score is now non-zero
        resp2 = client.get(f"/entities/{entity_id}/attention", headers=auth_headers)
        assert resp2.status_code == 200
        body = resp2.json()
        assert body["summary"]["attention_score"] > 0
        assert body["summary"]["total_mentions"] == 15
