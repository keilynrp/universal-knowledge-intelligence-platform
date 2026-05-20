import json

from backend import models
from backend.services.semantic_keyword_signal_engine import materialize_keyword_signals


def test_keyword_signal_engine_classifies_long_tail_and_external_support(db_session):
    attrs = {
        "abstract": "Open educational resources in rural universities are gaining policy attention.",
        "keywords": "open educational resources; rural universities",
        "external_attention_observations": [
            {
                "source_type": "policy",
                "mention_count": 3,
                "title": "Open educational resources in rural universities",
                "description": "Policy brief about rural universities.",
            }
        ],
    }
    db_session.add(models.RawEntity(
        primary_label="Rural OER Policy",
        domain="semantic_signals",
        enrichment_concepts="open educational resources, rural universities",
        attributes_json=json.dumps(attrs),
    ))
    db_session.commit()

    payload = materialize_keyword_signals(db_session, "semantic_signals", org_id=None, persist=False)
    signals = {row["keyword"]: row for row in payload["signals"]}

    assert payload["corpus_size"] == 1
    assert "open educational resources" in signals
    assert signals["open educational resources"]["classification"] == "long_tail"
    assert signals["open educational resources"]["external_support"] == 3
    assert "policy" in signals["open educational resources"]["external_source_types"]


def test_keyword_signal_endpoint_persists_entity_evidence(client, auth_headers, db_session):
    entity = models.RawEntity(
        primary_label="Knowledge Graph Opportunity",
        domain="semantic_endpoint",
        enrichment_concepts="knowledge graph, opportunity signal",
        attributes_json=json.dumps({
            "abstract": "Knowledge graph opportunity signal analysis for research portfolios.",
        }),
    )
    db_session.add(entity)
    db_session.commit()

    response = client.post("/analytics/keywords/semantic_endpoint/materialize?limit=10", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_candidates"] > 0

    db_session.refresh(entity)
    attrs = json.loads(entity.attributes_json)
    persisted = attrs.get("semantic_keyword_signals")
    assert persisted
    assert persisted[0]["evidence"]["model_version"] == payload["model_version"]


def test_keyword_signal_preview_does_not_persist(client, auth_headers, db_session):
    entity = models.RawEntity(
        primary_label="Preview Keyword Signal",
        domain="semantic_preview",
        enrichment_concepts="preview keyword signal",
    )
    db_session.add(entity)
    db_session.commit()

    response = client.get("/analytics/keywords/semantic_preview/signals?limit=5", headers=auth_headers)

    assert response.status_code == 200
    db_session.refresh(entity)
    attrs = json.loads(entity.attributes_json or "{}")
    assert "semantic_keyword_signals" not in attrs


def test_graph_materialize_returns_keyword_signal_summary(client, auth_headers, db_session):
    entity = models.RawEntity(
        primary_label="Graph Signal Record",
        domain="graph_semantic",
        import_batch_id=778,
        enrichment_concepts="graph signal, semantic keyword",
        attributes_json=json.dumps({"abstract": "Graph signal semantic keyword analysis."}),
    )
    db_session.add(entity)
    db_session.commit()

    response = client.post("/graph/materialize?domain=graph_semantic", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert "keyword_signals" in payload
    assert payload["keyword_signals"]["total_candidates"] > 0
