import json
from datetime import datetime, timezone

from backend import models
from backend.analyzers.external_attention import (
    attention_category,
    compute_attention_summary,
)


def test_attention_category_mapping():
    assert attention_category(0) == "none"
    assert attention_category(12) == "low"
    assert attention_category(37) == "moderate"
    assert attention_category(67) == "high"
    assert attention_category(88) == "very_high"


def test_compute_attention_summary_empty_data():
    payload = compute_attention_summary("{}")

    assert payload["summary"]["attention_score"] == 0
    assert payload["summary"]["category"] == "none"
    assert payload["summary"]["total_mentions"] == 0
    assert payload["source_counts"] == {}


def test_compute_attention_summary_weights_sources():
    attrs = {
        "external_attention_observations": [
            {"source_type": "policy", "mention_count": 2, "last_seen_at": "2026-05-01T00:00:00Z"},
            {"source_type": "social-web", "mention_count": 10, "last_seen_at": "2026-05-01T00:00:00Z"},
        ]
    }

    payload = compute_attention_summary(json.dumps(attrs))

    assert payload["summary"]["attention_score"] > 0
    assert payload["summary"]["total_mentions"] == 12
    assert payload["summary"]["active_sources"] == 2
    assert payload["source_counts"] == {"policy": 2, "social_web": 10}
    assert payload["source_breakdown"][0]["source_type"] == "policy"
    assert payload["source_breakdown"][0]["weighted_contribution"] > payload["source_breakdown"][1]["weighted_contribution"]
    assert round(sum(row["share"] for row in payload["source_breakdown"]), 2) == 1.0


def test_compute_attention_summary_caps_score():
    attrs = {
        "external_attention": [
            {"source_type": "policy", "mention_count": 100000, "last_seen_at": datetime.now(timezone.utc).isoformat()},
            {"source_type": "news", "mention_count": 100000, "last_seen_at": datetime.now(timezone.utc).isoformat()},
        ]
    }

    payload = compute_attention_summary(json.dumps(attrs))

    assert payload["summary"]["attention_score"] == 100
    assert payload["summary"]["category"] == "very_high"


def test_entity_attention_endpoint(client, session_factory, auth_headers):
    attrs = {
        "external_attention_observations": [
            {"source_type": "news", "mention_count": 3, "last_seen_at": "2026-05-01T00:00:00Z"},
            {"source_type": "repository", "mention_count": 1, "last_seen_at": "2026-04-20T00:00:00Z"},
        ]
    }
    with session_factory() as db:
        entity = models.RawEntity(
            domain="science",
            primary_label="Open Science Signal",
            attributes_json=json.dumps(attrs),
        )
        db.add(entity)
        db.commit()
        entity_id = entity.id

    response = client.get(f"/entities/{entity_id}/attention", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["scope"]["entity_id"] == entity_id
    assert body["summary"]["attention_score"] > 0
    assert body["summary"]["total_mentions"] == 4
    assert body["source_counts"] == {"news": 3, "repository": 1}
    assert [row["source_type"] for row in body["source_breakdown"]] == ["news", "repository"]


def test_compute_attention_summary_maps_unknown_source_to_other():
    attrs = {
        "external_attention_observations": [
            {"source_type": "newsletter", "mention_count": 2, "last_seen_at": "2026-05-01T00:00:00Z"},
        ]
    }

    payload = compute_attention_summary(json.dumps(attrs))

    assert payload["source_counts"] == {"other": 2}
    assert payload["source_breakdown"][0]["source_type"] == "other"


def test_compute_attention_summary_builds_monthly_timeline():
    attrs = {
        "external_attention_observations": [
            {"source_type": "news", "mention_count": 1, "last_seen_at": "2026-03-10T00:00:00Z"},
            {"source_type": "news", "mention_count": 2, "last_seen_at": "2026-03-18T00:00:00Z"},
            {"source_type": "policy", "mention_count": 3, "last_seen_at": "2026-04-02T00:00:00Z"},
        ]
    }

    payload = compute_attention_summary(json.dumps(attrs))

    assert [bucket["period"] for bucket in payload["timeline"]] == ["2026-03", "2026-04"]
    assert payload["timeline"][0]["mentions"] == 3
    assert payload["timeline"][0]["top_source_type"] == "news"
    assert payload["timeline"][1]["top_source_type"] == "policy"


def test_compute_attention_summary_marks_spike():
    attrs = {
        "external_attention_observations": [
            {"source_type": "social_web", "mention_count": 1, "last_seen_at": "2026-01-10T00:00:00Z"},
            {"source_type": "social_web", "mention_count": 1, "last_seen_at": "2026-02-10T00:00:00Z"},
            {"source_type": "policy", "mention_count": 8, "last_seen_at": "2026-03-10T00:00:00Z"},
        ]
    }

    payload = compute_attention_summary(json.dumps(attrs))

    assert payload["timeline"][-1]["spike"] is True
    assert payload["timeline"][-1]["spike_reason"] == "attention above rolling baseline"


def test_compute_attention_summary_explains_policy_and_spike():
    attrs = {
        "external_attention_observations": [
            {"source_type": "social_web", "mention_count": 1, "last_seen_at": "2026-01-10T00:00:00Z"},
            {"source_type": "blog", "mention_count": 1, "last_seen_at": "2026-02-10T00:00:00Z"},
            {"source_type": "policy", "mention_count": 8, "last_seen_at": "2026-03-10T00:00:00Z"},
        ]
    }

    payload = compute_attention_summary(json.dumps(attrs))
    explanation_types = [item["type"] for item in payload["explanations"]]

    assert "policy_mention" in explanation_types
    assert "attention_spike" in explanation_types
    assert "cross_source_momentum" in explanation_types
    assert len(payload["explanations"]) <= 5


def test_compute_attention_summary_returns_alerts_by_priority():
    attrs = {
        "external_attention_observations": [
            {"source_type": "social_web", "mention_count": 1, "last_seen_at": "2026-01-10T00:00:00Z"},
            {"source_type": "blog", "mention_count": 1, "last_seen_at": "2026-02-10T00:00:00Z"},
            {"source_type": "policy", "mention_count": 8, "last_seen_at": "2026-03-10T00:00:00Z"},
        ]
    }

    payload = compute_attention_summary(json.dumps(attrs))
    alert_types = [item["type"] for item in payload["alerts"]]

    assert alert_types[:3] == ["policy_mention", "attention_spike", "cross_source_momentum"]
    assert payload["alerts"][0]["severity"] == "high"
    assert payload["alerts"][0]["confidence"] == "high"


def test_compute_attention_summary_returns_new_attention_alert():
    attrs = {
        "external_attention_observations": [
            {"source_type": "news", "mention_count": 2, "last_seen_at": "2026-05-10T00:00:00Z"},
        ]
    }

    payload = compute_attention_summary(json.dumps(attrs))

    assert payload["alerts"][0]["type"] == "new_attention"
    assert payload["alerts"][0]["period"] == "2026-05"
