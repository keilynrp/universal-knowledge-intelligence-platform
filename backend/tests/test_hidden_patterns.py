import json

from backend import models
from backend.services.pattern_discovery import PatternDiscoveryService


def _seed_pattern_entities(db_session):
    rows = [
        ("Graph Learning for Research Intelligence", "knowledge graph; AI", 420, 0.91, "openalex"),
        ("Knowledge Graphs and Institutional Analytics", "knowledge graph; analytics", 380, 0.88, "openalex"),
        ("Graph Learning for Research Intelligence", "knowledge graph; AI", 35, 0.34, "wos"),
        ("Semantic Search for Library Discovery", "semantic search; metadata", 24, 0.41, "wos"),
        ("Metadata Quality in Research Portfolios", "metadata; authority control", 12, 0.39, "wos"),
        ("Authority Control for Research Records", "authority control; metadata", 8, 0.82, "scopus"),
    ]
    entities = []
    for title, concepts, citations, quality, provider in rows:
        entity = models.RawEntity(
            domain="science",
            entity_type="publication",
            primary_label=title,
            enrichment_status="completed",
            enrichment_citation_count=citations,
            enrichment_concepts=concepts,
            enrichment_source=provider,
            quality_score=quality,
            attributes_json=json.dumps({"provider": provider, "keywords": concepts}),
        )
        db_session.add(entity)
        entities.append(entity)
    db_session.commit()
    db_session.add(models.EntityRelationship(
        source_id=entities[0].id,
        target_id=entities[1].id,
        relation_type="related-to",
        weight=1.0,
    ))
    db_session.add(models.EntityRelationship(
        source_id=entities[0].id,
        target_id=entities[3].id,
        relation_type="has-concept",
        weight=1.0,
    ))
    db_session.add(models.EntityRelationship(
        source_id=entities[0].id,
        target_id=entities[5].id,
        relation_type="related-to",
        weight=1.0,
    ))
    db_session.commit()
    return entities


def test_pattern_discovery_returns_explainable_contract(db_session):
    _seed_pattern_entities(db_session)

    result = PatternDiscoveryService.discover(db_session, domain_id="science", org_id=None, limit=6)

    assert result["summary"]["records_analyzed"] == 6
    assert result["summary"]["patterns_found"] > 0
    pattern = result["patterns"][0]
    assert {"id", "type", "label", "confidence", "impact_score", "evidence", "entities", "recommended_action"} <= set(pattern)
    assert pattern["confidence"] in {"high", "medium", "low"}
    assert 0 <= pattern["impact_score"] <= 100


def test_patterns_endpoint_supports_domain_filter(client, auth_headers, db_session):
    _seed_pattern_entities(db_session)

    response = client.get("/analytics/patterns?domain_id=science&limit=6", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["domain_id"] == "science"
    assert payload["summary"]["records_analyzed"] == 6
    assert any(pattern["type"] in {"semantic_cluster", "impact_outlier"} for pattern in payload["patterns"])


def test_patterns_endpoint_supports_provider_filter(client, auth_headers, db_session):
    _seed_pattern_entities(db_session)

    response = client.get("/analytics/patterns?domain_id=science&provider=wos", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"]["provider"] == "wos"
    assert payload["summary"]["records_analyzed"] == 3
