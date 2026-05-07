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
