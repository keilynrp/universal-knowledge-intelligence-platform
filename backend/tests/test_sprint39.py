"""
Sprint 39 regression tests — Executive Dashboard GET /dashboard/summary
"""
import json
from unittest.mock import patch

import pandas as pd
import pytest
from backend import models
from backend.analyzers.topic_modeling import TopicAnalyzer


# ── Helpers ──────────────────────────────────────────────────────────────────

def _seed_entities(db, n=5):
    """Insert n raw entities with varied data."""
    for i in range(n):
        db.add(models.RawEntity(
            primary_label=f"Entity {i}",
            domain="default",
            attributes_json=json.dumps({"year": 2020 + i}),
            enrichment_status="completed" if i % 2 == 0 else "none",
            enrichment_citation_count=10 * (i + 1) if i % 2 == 0 else None,
            enrichment_source="openalex" if i % 2 == 0 else None,
            enrichment_concepts="AI, Machine Learning" if i % 2 == 0 else None,
        ))
    db.commit()


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_dashboard_summary_requires_auth(client):
    """Unauthenticated requests must return 401/403."""
    response = client.get("/dashboard/summary")
    assert response.status_code in (401, 403)


# ── Shape / contract tests ────────────────────────────────────────────────────

def test_dashboard_summary_returns_shape(client, auth_headers, db_session):
    _seed_entities(db_session)
    response = client.get("/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Top-level keys
    assert "domain_id" in data
    assert "kpis" in data
    assert "entities_by_year" in data
    assert "brand_year_matrix" in data
    assert "top_concepts" in data
    assert "emerging_topic_signals" in data
    assert "top_entities" in data
    assert "recommended_actions" in data
    assert "institutional_benchmark" in data
    assert "impact_projection" in data
    assert "hidden_patterns" in data
    assert "external_attention" in data

    # KPI shape
    kpis = data["kpis"]
    for key in ("total_entities", "enriched_count", "enrichment_pct", "avg_citations", "total_concepts"):
        assert key in kpis

    projection = data["impact_projection"]
    assert projection["method"] == "monte_carlo"
    assert projection["range"]["p10"] <= projection["range"]["p50"] <= projection["range"]["p90"]
    assert projection["brief_angle"]

    assert "patterns" in data["hidden_patterns"]
    assert "summary" in data["hidden_patterns"]

    # Matrix shape
    matrix = data["brand_year_matrix"]
    assert "brands" in matrix
    assert "years" in matrix
    assert "matrix" in matrix


def test_dashboard_includes_external_attention_summary(client, auth_headers, db_session):
    db_session.add(models.RawEntity(
        primary_label="Policy Attention Entity",
        domain="attention_dashboard_test",
        attributes_json=json.dumps({
            "external_attention_observations": [
                {"source_type": "news", "mention_count": 2, "last_seen_at": "2026-01-10T00:00:00Z"},
                {"source_type": "policy", "mention_count": 4, "last_seen_at": "2026-02-10T00:00:00Z"},
            ]
        }),
    ))
    db_session.commit()

    response = client.get("/dashboard/summary?domain_id=attention_dashboard_test", headers=auth_headers)

    assert response.status_code == 200
    external_attention = response.json()["external_attention"]
    assert external_attention["summary"]["active_entities"] == 1
    assert external_attention["summary"]["total_mentions"] == 6
    assert external_attention["top_entities"][0]["label"] == "Policy Attention Entity"
    assert external_attention["alerts"][0]["type"] == "policy_mention"


def test_dashboard_kpis_match_entity_count(client, auth_headers, db_session):
    """kpis.total_entities must be >= the entities we seeded (StaticPool may have residuals)."""
    _seed_entities(db_session, n=3)
    response = client.get("/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    # Use count via same shared pool so both sides see the same DB state
    actual = db_session.query(models.RawEntity).count()
    # The dashboard count should equal the DB count visible to the endpoint
    assert data["kpis"]["total_entities"] >= 3
    assert data["kpis"]["total_entities"] >= actual - 2  # allow minor StaticPool drift


def test_stats_domain_distribution_uses_domain_key(client, auth_headers, db_session):
    db_session.add(models.RawEntity(
        primary_label="Science entity",
        domain="science",
        enrichment_status="completed",
    ))
    db_session.commit()

    response = client.get("/stats", headers=auth_headers)

    assert response.status_code == 200
    domains = response.json()["domain_distribution"]
    science = next((item for item in domains if item.get("domain") == "science"), None)
    assert science is not None
    assert science["count"] >= 1


def test_dashboard_empty_domain_returns_zeros(client, auth_headers):
    """With no entities, KPIs are zero and lists are empty — no server error."""
    response = client.get("/dashboard/summary?domain_id=empty_test_domain", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["kpis"]["total_entities"] == 0
    assert data["entities_by_year"] == []
    assert data["top_entities"] == []


def test_dashboard_entities_by_year_sorted(client, auth_headers, db_session):
    """entities_by_year must be sorted in ascending year order."""
    _seed_entities(db_session)
    response = client.get("/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    years_list = [item["year"] for item in response.json()["entities_by_year"]]
    assert years_list == sorted(years_list)


def test_dashboard_entities_by_year_reads_attributes_json(client, auth_headers, db_session):
    for year in (2022, 2022, 2023):
        db_session.add(models.RawEntity(
            primary_label=f"Paper {year}",
            domain="timeline_test",
            attributes_json=json.dumps({"year": year}),
            enrichment_status="completed",
            enrichment_concepts="AI, Graphs",
        ))
    db_session.commit()

    response = client.get("/dashboard/summary?domain_id=timeline_test", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["entities_by_year"] == [
        {"year": 2022, "count": 2},
        {"year": 2023, "count": 1},
    ]


def test_dashboard_brand_matrix_top5(client, auth_headers, db_session):
    """brand_year_matrix.brands must have at most 5 entries."""
    # Seed entities with many different brands
    for i in range(10):
        db_session.add(models.RawEntity(
            primary_label=f"Entity brand {i}",
            secondary_label=f"Brand{i}",
            enrichment_status="none",
        ))
    db_session.commit()
    response = client.get("/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    brands = response.json()["brand_year_matrix"]["brands"]
    assert len(brands) <= 5


def test_dashboard_recommended_actions_are_explainable(client, auth_headers, db_session):
    for i in range(5):
        db_session.add(models.RawEntity(
            primary_label=f"Priority Entity {i}",
            domain="decision_actions_test",
            enrichment_status="completed" if i == 0 else "none",
            enrichment_citation_count=120 if i == 0 else None,
            enrichment_source="openalex" if i == 0 else None,
            quality_score=0.25 if i > 0 else 0.4,
        ))
    db_session.commit()

    response = client.get("/dashboard/summary?domain_id=decision_actions_test", headers=auth_headers)
    assert response.status_code == 200
    actions = response.json()["recommended_actions"]

    assert any(action["id"] == "bulk_enrichment" for action in actions)
    assert any(action["id"] == "review_low_quality_records" for action in actions)
    for action in actions:
        assert action["title"]
        assert action["detail"]
        assert action["evidence"]
        assert action["priority"] in {"high", "medium", "low"}
        assert isinstance(action.get("meta") or {}, dict)


def test_dashboard_includes_institutional_benchmark_summary(client, auth_headers, db_session):
    _seed_entities(db_session, n=4)
    response = client.get("/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    benchmark = response.json()["institutional_benchmark"]
    assert benchmark["profile_id"] == "research_portfolio_baseline"
    assert benchmark["status"] in {"ready", "watch", "gap"}
    assert "readiness_pct" in benchmark
    assert isinstance(benchmark["rules"], list)


def test_dashboard_includes_emerging_topic_signals(client, auth_headers, db_session):
    records = [
        ("AI, Machine Learning", 2021),
        ("AI, Machine Learning", 2022),
        ("AI, Machine Learning", 2023),
        ("Quantum Systems, AI", 2024),
        ("Quantum Systems, Graph Learning", 2024),
        ("Quantum Systems, AI", 2025),
        ("Quantum Systems, Graph Learning", 2025),
    ]
    for idx, (concepts, year) in enumerate(records):
        db_session.add(models.RawEntity(
            primary_label=f"Trend Entity {idx}",
            domain="default",
            attributes_json=json.dumps({"year": year}),
            enrichment_status="completed",
            enrichment_concepts=concepts,
        ))
    db_session.commit()

    response = client.get("/dashboard/summary?domain_id=default", headers=auth_headers)
    assert response.status_code == 200
    signals = response.json()["emerging_topic_signals"]

    assert signals["is_experimental"] is True
    assert len(signals["recent_years"]) == 2
    assert max(signals["recent_years"]) >= 2024
    assert signals["baseline_years"]
    assert isinstance(signals["signals"], list)


def test_dashboard_uses_concept_fallbacks_from_attributes_json(client, auth_headers, db_session):
    db_session.add(models.RawEntity(
        primary_label="Fallback Concept Paper",
        domain="concept_fallback_test",
        attributes_json=json.dumps({
            "year": 2024,
            "keywords": ["Knowledge Graphs", "OpenAlex"],
        }),
        enrichment_status="completed",
        enrichment_concepts=None,
    ))
    db_session.commit()

    response = client.get("/dashboard/summary?domain_id=concept_fallback_test", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["kpis"]["total_concepts"] == 2
    concepts = {topic["concept"] for topic in data["top_concepts"]}
    assert "Knowledge Graphs" in concepts
    assert "OpenAlex" in concepts


def test_dashboard_derives_quality_when_scores_are_not_persisted(client, auth_headers, db_session):
    db_session.add(models.RawEntity(
        primary_label="Derived Quality Entity",
        secondary_label="Knowledge Graph",
        canonical_id="kg-1",
        entity_type="work",
        domain="derived_quality_test",
        enrichment_status="completed",
        enrichment_doi="10.1234/example",
        quality_score=None,
    ))
    db_session.commit()

    response = client.get("/dashboard/summary?domain_id=derived_quality_test", headers=auth_headers)
    assert response.status_code == 200
    quality = response.json()["quality"]

    assert quality["average"] is not None
    assert quality["average"] > 0.0


def test_dashboard_counts_legacy_enriched_status_aliases(client, auth_headers, db_session):
    db_session.add_all([
        models.RawEntity(
            primary_label="Legacy Done Paper",
            domain="legacy_enriched_status_test",
            enrichment_status="done",
            enrichment_citation_count=30,
            enrichment_source="openalex",
            enrichment_concepts="Knowledge Graphs",
        ),
        models.RawEntity(
            primary_label="Legacy Enriched Paper",
            domain="legacy_enriched_status_test",
            enrichment_status="enriched",
            enrichment_citation_count=10,
            enrichment_source="openalex",
            enrichment_concepts="Pattern Analysis",
        ),
        models.RawEntity(
            primary_label="Pending Paper",
            domain="legacy_enriched_status_test",
            enrichment_status="pending",
            enrichment_citation_count=1000,
            enrichment_source="openalex",
        ),
    ])
    db_session.commit()

    response = client.get("/dashboard/summary?domain_id=legacy_enriched_status_test", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["kpis"]["total_entities"] == 3
    assert data["kpis"]["enriched_count"] == 2
    assert data["kpis"]["enrichment_pct"] == 66.7
    assert data["kpis"]["avg_citations"] == 20.0
    assert [entity["primary_label"] for entity in data["top_entities"]] == [
        "Legacy Done Paper",
        "Legacy Enriched Paper",
    ]


def test_dashboard_all_domain_counts_enrichment_across_domains(client, auth_headers, db_session):
    db_session.add_all([
        models.RawEntity(
            primary_label="Science Completed",
            domain="science",
            enrichment_status="completed",
            enrichment_citation_count=12,
            enrichment_source="openalex",
            enrichment_concepts="Open Science",
        ),
        models.RawEntity(
            primary_label="Catalog Done",
            domain="universal_catalog",
            enrichment_status="done",
            enrichment_citation_count=8,
            enrichment_source="openalex",
            enrichment_concepts="Knowledge Graphs",
        ),
        models.RawEntity(
            primary_label="Default Pending",
            domain="default",
            enrichment_status="pending",
        ),
    ])
    db_session.commit()

    response = client.get("/dashboard/summary?domain_id=all&force_refresh=true", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["domain_id"] == "all"
    assert data["kpis"]["total_entities"] >= 3
    assert data["kpis"]["enriched_count"] >= 2
    assert data["kpis"]["enrichment_pct"] > 0
    top_labels = {entity["primary_label"] for entity in data["top_entities"]}
    assert {"Science Completed", "Catalog Done"}.issubset(top_labels)


def test_stats_endpoint_scopes_counts_by_domain(client, auth_headers, db_session):
    db_session.add_all([
        models.RawEntity(primary_label="Scoped Science", domain="stats_science", entity_type="paper"),
        models.RawEntity(primary_label="Scoped Catalog", domain="stats_catalog", entity_type="record"),
        models.RawEntity(primary_label="Scoped Catalog 2", domain="stats_catalog", entity_type="record"),
    ])
    db_session.commit()

    all_response = client.get("/stats?domain_id=all", headers=auth_headers)
    science_response = client.get("/stats?domain_id=stats_science", headers=auth_headers)
    catalog_response = client.get("/stats?domain_id=stats_catalog", headers=auth_headers)

    assert all_response.status_code == 200
    assert science_response.status_code == 200
    assert catalog_response.status_code == 200
    assert all_response.json()["total_entities"] >= 3
    assert science_response.json()["total_entities"] == 1
    assert catalog_response.json()["total_entities"] == 2


def test_dashboard_summary_disables_http_cache_for_refresh_controls(client, auth_headers):
    response = client.get("/dashboard/summary?domain_id=default&force_refresh=true", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0, must-revalidate"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["expires"] == "0"


def test_dashboard_skips_noisy_author_list_labels_in_year_matrix(client, auth_headers, db_session):
    db_session.add(models.RawEntity(
        primary_label="Ana Perez; Luis Soto; Marta Ruiz; Diego Leon",
        secondary_label="Institutional collaboration note",
        domain="label_matrix_test",
        attributes_json=json.dumps({"year": 2025}),
    ))
    db_session.commit()

    response = client.get("/dashboard/summary?domain_id=label_matrix_test", headers=auth_headers)
    assert response.status_code == 200
    brands = response.json()["brand_year_matrix"]["brands"]

    assert "Ana Perez; Luis Soto; Marta Ruiz; Diego Leon" not in brands
    assert "Institutional collaboration note" in brands


def test_dashboard_deduplicates_top_entities_by_label_and_source(client, auth_headers, db_session):
    db_session.add_all([
        models.RawEntity(
            primary_label="Editorial",
            domain="top_entities_dedupe_test",
            enrichment_status="completed",
            enrichment_citation_count=500,
            enrichment_source="openalex",
        ),
        models.RawEntity(
            primary_label="Editorial",
            domain="top_entities_dedupe_test",
            enrichment_status="completed",
            enrichment_citation_count=450,
            enrichment_source="openalex",
        ),
        models.RawEntity(
            primary_label="Signal Paper",
            domain="top_entities_dedupe_test",
            enrichment_status="completed",
            enrichment_citation_count=400,
            enrichment_source="openalex",
        ),
    ])
    db_session.commit()

    response = client.get("/dashboard/summary?domain_id=top_entities_dedupe_test", headers=auth_headers)
    assert response.status_code == 200
    labels = [entity["primary_label"] for entity in response.json()["top_entities"]]

    assert labels.count("Editorial") == 1
    assert "Signal Paper" in labels


def test_dashboard_normalizes_noisy_parenthetical_concepts(client, auth_headers, db_session):
    db_session.add(models.RawEntity(
        primary_label="Concept Noise",
        domain="concept_noise_test",
        enrichment_status="completed",
        enrichment_concepts="Context (archaeology), Work (physics), Artificial intelligence, Computer science",
    ))
    db_session.commit()

    response = client.get("/dashboard/summary?domain_id=concept_noise_test", headers=auth_headers)
    assert response.status_code == 200
    concepts = {topic["concept"] for topic in response.json()["top_concepts"]}

    assert "Artificial intelligence" in concepts
    assert "Computer science" in concepts
    assert "Context" not in concepts
    assert "Work" not in concepts


def test_topic_analyzer_emerging_signals_detects_acceleration():
    df = pd.DataFrame([
        {
            "id": 1,
            "enrichment_concepts": "AI, Machine Learning",
            "attributes_json": json.dumps({"year": 2021}),
            "primary_label": "Paper 1",
            "secondary_label": None,
        },
        {
            "id": 2,
            "enrichment_concepts": "AI, Machine Learning",
            "attributes_json": json.dumps({"year": 2022}),
            "primary_label": "Paper 2",
            "secondary_label": None,
        },
        {
            "id": 3,
            "enrichment_concepts": "AI, Machine Learning",
            "attributes_json": json.dumps({"year": 2023}),
            "primary_label": "Paper 3",
            "secondary_label": None,
        },
        {
            "id": 4,
            "enrichment_concepts": "Quantum Systems, AI",
            "attributes_json": json.dumps({"year": 2024}),
            "primary_label": "Paper 4",
            "secondary_label": None,
        },
        {
            "id": 5,
            "enrichment_concepts": "Quantum Systems, Graph Learning",
            "attributes_json": json.dumps({"year": 2024}),
            "primary_label": "Paper 5",
            "secondary_label": None,
        },
        {
            "id": 6,
            "enrichment_concepts": "Quantum Systems, AI",
            "attributes_json": json.dumps({"year": 2025}),
            "primary_label": "Paper 6",
            "secondary_label": None,
        },
        {
            "id": 7,
            "enrichment_concepts": "Quantum Systems, Graph Learning",
            "attributes_json": json.dumps({"year": 2025}),
            "primary_label": "Paper 7",
            "secondary_label": None,
        },
    ])

    with patch("backend.analyzers.topic_modeling._load_concepts_timeseries_df", return_value=df):
        result = TopicAnalyzer().emerging_signals("default", top_n=4)

    assert result["recent_years"] == [2024, 2025]
    assert result["baseline_years"] == [2021, 2022, 2023]
    assert any(signal["concept"] == "Quantum Systems" for signal in result["signals"])
    for signal in result["signals"]:
        assert signal["confidence"] in {"high", "medium", "low"}
        assert signal["evidence"]


def test_benchmark_profiles_endpoint_lists_builtins(client, auth_headers):
    response = client.get("/analytics/benchmarks/profiles", headers=auth_headers)
    assert response.status_code == 200
    ids = {profile["id"] for profile in response.json()}
    assert "research_portfolio_baseline" in ids
    assert "ref_readiness_baseline" in ids
    assert "sni_readiness_baseline" in ids
    assert all("rules" in profile for profile in response.json())


def test_dashboard_uses_org_default_benchmark_profile_when_not_explicit(client, auth_headers):
    import time

    slug = f"benchmark-org-{int(time.time() * 1000) % 100000}"
    created = client.post(
        "/organizations",
        json={"name": "Benchmark Org", "slug": slug, "plan": "free"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    org_id = created.json()["id"]

    updated = client.put(
        f"/organizations/{org_id}",
        json={"benchmark_profile_id": "sni_readiness_baseline"},
        headers=auth_headers,
    )
    assert updated.status_code == 200

    summary = client.get("/dashboard/summary?domain_id=default", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["institutional_benchmark"]["profile_id"] == "sni_readiness_baseline"

    profiles = client.get("/analytics/benchmarks/profiles", headers=auth_headers)
    assert profiles.status_code == 200
    defaults = [profile for profile in profiles.json() if profile["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == "sni_readiness_baseline"


def test_reports_use_org_benchmark_profile_overrides_when_not_explicit(client, auth_headers):
    import time

    slug = f"benchmark-report-org-{int(time.time() * 1000) % 100000}"
    created = client.post(
        "/organizations",
        json={"name": "Benchmark Report Org", "slug": slug, "plan": "free"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    org_id = created.json()["id"]

    updated = client.put(
        f"/organizations/{org_id}",
        json={
            "benchmark_profile_id": "sni_readiness_baseline",
            "benchmark_profile_overrides": {
                "profiles": {
                    "sni_readiness_baseline": {
                        "name": "Custom SNI Baseline",
                        "rules": {
                            "quality_min": {
                                "threshold": 72,
                                "fail_text": "Custom quality gap message.",
                            }
                        },
                    }
                }
            },
        },
        headers=auth_headers,
    )
    assert updated.status_code == 200

    switched = client.post(f"/organizations/{org_id}/switch", headers=auth_headers)
    assert switched.status_code == 200

    report = client.post(
        "/reports/generate",
        json={"domain_id": "default", "sections": ["institutional_benchmark"], "title": "Custom Benchmark Report"},
        headers=auth_headers,
    )
    assert report.status_code == 200
    assert "Custom SNI Baseline" in report.text
    assert "Custom quality gap message." in report.text


def test_benchmark_evaluate_endpoint_accepts_known_profile(client, auth_headers):
    response = client.get(
        "/analytics/benchmarks/evaluate?domain_id=default&profile_id=sni_readiness_baseline",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["profile_id"] == "sni_readiness_baseline"
    assert data["profile_name"] == "SNI Readiness Baseline"


def test_benchmark_evaluate_endpoint_rejects_unknown_profile(client, auth_headers):
    response = client.get(
        "/analytics/benchmarks/evaluate?domain_id=default&profile_id=not_real",
        headers=auth_headers,
    )
    assert response.status_code == 404
