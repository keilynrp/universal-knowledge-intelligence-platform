import json
from datetime import datetime, timezone

from backend import models
from backend.services.graph_materializer import materialize_scientific_import_graph


def _create_science_batch(db_session, *, provider: str = "wos") -> models.ImportBatch:
    batch = models.ImportBatch(
        org_id=None,
        domain_id="science",
        source_type=f"science_upload:{provider}",
        file_name="science.txt",
        file_format="wos_plaintext",
        source_label="science.txt",
        total_rows=1,
        entity_type_hint="publication",
        created_by=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(batch)
    db_session.flush()
    return batch


def _create_publication(db_session, batch: models.ImportBatch) -> models.RawEntity:
    attrs = {
        "provider": "wos",
        "provider_record_id": "WOS:123",
        "journal": "Journal of Knowledge Graphs",
        "canonical_authors": [
            {"name": "Ada Lovelace", "order": 1, "orcid": "0000-0001", "affiliations": ["Open Science Lab"]},
            {"name": "Grace Hopper", "order": 2, "external_id": "A-2", "affiliations": ["Open Science Lab"]},
        ],
        "canonical_affiliations": [
            {"name": "Open Science Lab", "country": "US", "external_id": "ror:abc"},
        ],
        "canonical_identifiers": [
            {"scheme": "wos", "value": "WOS:123"},
        ],
        "raw_record": {"keywords": "knowledge graph; research intelligence"},
    }
    publication = models.RawEntity(
        org_id=None,
        import_batch_id=batch.id,
        domain="science",
        entity_type="publication",
        primary_label="Knowledge Graphs for Research Intelligence",
        secondary_label="Ada Lovelace; Grace Hopper",
        canonical_id="doi:10.123/example",
        attributes_json=json.dumps(attrs),
        enrichment_doi="10.123/example",
        enrichment_concepts="semantic intelligence",
        enrichment_source="wos",
        source="user",
    )
    db_session.add(publication)
    db_session.commit()
    return publication


def test_materializes_scientific_import_graph(db_session):
    batch = _create_science_batch(db_session)
    publication = _create_publication(db_session, batch)

    result = materialize_scientific_import_graph(db_session, batch.id, org_id=None)

    assert result["publications"] == 1
    assert result["nodes_created"] >= 7
    assert result["relationships_created"] >= 8

    labels = {
        row.primary_label
        for row in db_session.query(models.RawEntity).filter(models.RawEntity.import_batch_id == batch.id).all()
    }
    assert "Ada Lovelace" in labels
    assert "Grace Hopper" in labels
    assert "Open Science Lab" in labels
    assert "Journal of Knowledge Graphs" in labels
    assert "knowledge graph" in labels

    relation_types = {
        row.relation_type
        for row in db_session.query(models.EntityRelationship).all()
    }
    assert "authored-by" in relation_types
    assert "belongs-to" in relation_types
    assert "published-in" in relation_types
    assert "has-concept" in relation_types
    assert "identified-by" in relation_types
    assert "coauthor-with" in relation_types

    result_again = materialize_scientific_import_graph(db_session, batch.id, org_id=None)
    assert result_again["nodes_created"] == 0
    assert result_again["relationships_created"] == 0

    assert (
        db_session.query(models.EntityRelationship)
        .filter(models.EntityRelationship.source_id == publication.id)
        .count()
        >= 5
    )


def test_graph_visualization_filters_by_import_batch(client, auth_headers, db_session):
    included_batch = _create_science_batch(db_session, provider="wos")
    _create_publication(db_session, included_batch)
    excluded_batch = _create_science_batch(db_session, provider="openalex")
    excluded = models.RawEntity(
        org_id=None,
        import_batch_id=excluded_batch.id,
        domain="science",
        entity_type="publication",
        primary_label="Excluded Publication",
        canonical_id="openalex:excluded",
        enrichment_source="openalex",
        attributes_json=json.dumps({"provider": "openalex"}),
        source="user",
    )
    db_session.add(excluded)
    db_session.commit()
    materialize_scientific_import_graph(db_session, included_batch.id, org_id=None)
    materialize_scientific_import_graph(db_session, excluded_batch.id, org_id=None)

    response = client.get(
        f"/graph/visualization?import_batch_id={included_batch.id}&limit=100",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    labels = {node["label"] for node in payload["nodes"]}
    assert "Knowledge Graphs for Research Intelligence" in labels
    assert "Excluded Publication" not in labels
    assert payload["filters"]["import_batch_id"] == included_batch.id


def test_graph_visualization_scopes_by_domain_and_treats_all_as_aggregate(client, auth_headers, db_session):
    science_a = models.RawEntity(primary_label="Science A", domain="graph_science", entity_type="publication")
    science_b = models.RawEntity(primary_label="Science B", domain="graph_science", entity_type="publication")
    business_a = models.RawEntity(primary_label="Business A", domain="graph_business", entity_type="publication")
    business_b = models.RawEntity(primary_label="Business B", domain="graph_business", entity_type="publication")
    db_session.add_all([science_a, science_b, business_a, business_b])
    db_session.flush()
    db_session.add_all([
        models.EntityRelationship(source_id=science_a.id, target_id=science_b.id, relation_type="cites", weight=1.0),
        models.EntityRelationship(source_id=business_a.id, target_id=business_b.id, relation_type="cites", weight=1.0),
    ])
    db_session.commit()

    scoped = client.get("/graph/visualization?domain=graph_science&limit=100", headers=auth_headers)
    aggregate = client.get("/graph/visualization?domain=all&limit=100", headers=auth_headers)

    assert scoped.status_code == 200
    scoped_labels = {node["label"] for node in scoped.json()["nodes"]}
    assert {"Science A", "Science B"} <= scoped_labels
    assert "Business A" not in scoped_labels
    assert scoped.json()["filters"]["domain"] == "graph_science"

    assert aggregate.status_code == 200
    aggregate_labels = {node["label"] for node in aggregate.json()["nodes"]}
    assert {"Science A", "Science B", "Business A", "Business B"} <= aggregate_labels
    assert aggregate.json()["filters"]["domain"] is None


def test_graph_path_respects_domain_scope(client, auth_headers, db_session):
    science_a = models.RawEntity(primary_label="Path Science A", domain="path_science", entity_type="publication")
    science_b = models.RawEntity(primary_label="Path Science B", domain="path_science", entity_type="publication")
    business_mid = models.RawEntity(primary_label="Path Business Mid", domain="path_business", entity_type="publication")
    db_session.add_all([science_a, science_b, business_mid])
    db_session.flush()
    db_session.add_all([
        models.EntityRelationship(source_id=science_a.id, target_id=business_mid.id, relation_type="related-to", weight=1.0),
        models.EntityRelationship(source_id=business_mid.id, target_id=science_b.id, relation_type="related-to", weight=1.0),
    ])
    db_session.commit()

    aggregate = client.get(f"/graph/path?from_id={science_a.id}&to_id={science_b.id}&domain=all", headers=auth_headers)
    scoped = client.get(f"/graph/path?from_id={science_a.id}&to_id={science_b.id}&domain=path_science", headers=auth_headers)

    assert aggregate.status_code == 200
    assert aggregate.json()["found"] is True
    assert scoped.status_code == 200
    assert scoped.json()["found"] is False


def test_materializer_uses_enrichment_metadata_for_existing_records(db_session):
    batch = _create_science_batch(db_session)
    publication = models.RawEntity(
        org_id=None,
        import_batch_id=batch.id,
        domain="science",
        entity_type="publication",
        primary_label="Enriched Graph Record",
        enrichment_doi="10.555/enriched",
        enrichment_concepts="graph enrichment, research intelligence",
        enrichment_source="openalex",
        enrichment_status="completed",
        attributes_json=json.dumps({
            "enrichment_authors": ["Ada Lovelace", "Grace Hopper"],
            "enrichment_author_orcids": ["0000-0001", "0000-0002"],
            "venue": "Journal of Enriched Graphs",
        }),
    )
    db_session.add(publication)
    db_session.commit()

    result = materialize_scientific_import_graph(db_session, batch.id, org_id=None)
    labels = {
        row.primary_label
        for row in db_session.query(models.RawEntity).filter(models.RawEntity.import_batch_id == batch.id).all()
    }
    relation_types = {
        row.relation_type
        for row in db_session.query(models.EntityRelationship).all()
    }

    assert result["relationships_created"] >= 6
    assert {"Ada Lovelace", "Grace Hopper", "Journal of Enriched Graphs", "graph enrichment"} <= labels
    assert {"authored-by", "published-in", "has-concept", "identified-by", "coauthor-with"} <= relation_types


def test_graph_materialize_endpoint_backfills_existing_batch(client, auth_headers, db_session):
    batch = _create_science_batch(db_session)
    db_session.add(models.RawEntity(
        org_id=None,
        import_batch_id=batch.id,
        domain="science",
        entity_type="publication",
        primary_label="Backfill Graph Record",
        enrichment_doi="10.777/backfill",
        enrichment_concepts="backfill graph",
        enrichment_status="completed",
    ))
    db_session.commit()

    response = client.post(f"/graph/materialize?import_batch_id={batch.id}", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"]["batches"] == 1
    assert payload["totals"]["relationships_created"] >= 2


def test_entity_graph_diagnostics_explains_materializable_record(client, auth_headers, db_session):
    batch = _create_science_batch(db_session)
    entity = models.RawEntity(
        org_id=None,
        import_batch_id=batch.id,
        domain="science",
        entity_type="publication",
        primary_label="Diagnostic Graph Record",
        enrichment_concepts="diagnostic, graph",
        enrichment_status="completed",
    )
    db_session.add(entity)
    db_session.commit()

    response = client.get(f"/entities/{entity.id}/graph/diagnostics", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "materializable"
    assert payload["can_materialize"] is True
    assert payload["signals"]["concept_count"] == 2


def test_relationship_suggestions_use_shared_concepts(client, auth_headers, db_session):
    source = models.RawEntity(
        primary_label="Source Graph Paper",
        domain="suggestions",
        import_batch_id=91,
        enrichment_concepts="open science, graph analytics",
    )
    target = models.RawEntity(
        primary_label="Target Graph Paper",
        domain="suggestions",
        import_batch_id=91,
        enrichment_concepts="graph analytics, research intelligence",
    )
    db_session.add_all([source, target])
    db_session.commit()

    response = client.get(f"/entities/{source.id}/relationships/suggestions", headers=auth_headers)

    assert response.status_code == 200
    suggestions = response.json()["suggestions"]
    assert suggestions
    assert suggestions[0]["target_id"] == target.id
    assert suggestions[0]["relation_type"] == "related-to"
    assert "graph analytics" in suggestions[0]["reason"]


def test_manual_relationship_accepts_derived_relation_types(client, auth_headers, db_session):
    source = models.RawEntity(primary_label="Publication", domain="manual_graph")
    concept = models.RawEntity(primary_label="Knowledge Graph", domain="manual_graph", entity_type="concept")
    db_session.add_all([source, concept])
    db_session.commit()

    response = client.post(
        f"/entities/{source.id}/relationships",
        headers=auth_headers,
        json={"target_id": concept.id, "relation_type": "has-concept", "weight": 0.8},
    )

    assert response.status_code == 201
    assert response.json()["relation_type"] == "has-concept"
