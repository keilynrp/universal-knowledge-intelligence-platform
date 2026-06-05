"""Issue #32 — agentic-chat tenant context.

The agentic layer (tool_registry, ContextEngine, ChromaDB retrieval) did not
propagate the caller's org_id, leaking cross-tenant data into tool results and
LLM prompts. These tests pin the per-org boundary at each surface.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from backend import models
from backend.context_engine import ContextEngine
from backend.tool_registry import get_registry


def _org(db) -> int:
    suffix = uuid4().hex[:8]
    owner = models.User(
        username=f"owner_{suffix}",
        password_hash="x",
        role="admin",
        is_active=True,
    )
    db.add(owner)
    db.flush()
    org = models.Organization(
        name=f"Org {suffix}",
        slug=f"org-{suffix}",
        owner_id=owner.id,
        plan="pro",
        is_active=True,
    )
    db.add(org)
    db.flush()
    return org.id


def _entity(db, *, org_id, enriched: bool = True):
    db.add(
        models.RawEntity(
            org_id=org_id,
            primary_label=f"E-{uuid4().hex[:6]}",
            domain="default",
            entity_type="paper",
            source="test",
            validation_status="confirmed",
            enrichment_status="completed" if enriched else "pending",
            attributes_json="{}",
        )
    )


# ── tool_registry ───────────────────────────────────────────────────────────

def test_tool_entity_stats_scoped_to_org(db_session):
    org_a = _org(db_session)
    org_b = _org(db_session)
    for _ in range(3):
        _entity(db_session, org_id=org_a)
    for _ in range(7):
        _entity(db_session, org_id=org_b)
    db_session.commit()

    registry = get_registry()
    stats_a = registry.invoke("get_entity_stats", {"domain_id": "default"}, db_session, org_a)
    assert stats_a["total"] == 3  # org B's 7 must not leak in

    stats_b = registry.invoke("get_entity_stats", {"domain_id": "default"}, db_session, org_b)
    assert stats_b["total"] == 7

    # Global scope (super_admin) sees everything.
    stats_global = registry.invoke("get_entity_stats", {"domain_id": "default"}, db_session, None)
    assert stats_global["total"] >= 10


# ── ContextEngine ───────────────────────────────────────────────────────────

def test_context_engine_entity_stats_scoped(db_session):
    org_a = _org(db_session)
    org_b = _org(db_session)
    _entity(db_session, org_id=org_a)
    _entity(db_session, org_id=org_a)
    _entity(db_session, org_id=org_b)
    db_session.commit()

    ctx = ContextEngine().build_domain_context("default", db_session, org_a)
    assert ctx["entity_stats"]["total"] == 2  # only org A


# ── ChromaDB vector store query filter ──────────────────────────────────────

def _fake_collection():
    coll = MagicMock()
    coll.count.return_value = 5
    coll.query.return_value = {
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
        "ids": [[]],
    }
    return coll


def test_vector_query_adds_org_filter():
    from backend.analytics.vector_store import VectorStoreService

    coll = _fake_collection()
    with patch.object(VectorStoreService, "_get_collection", return_value=coll):
        VectorStoreService.query([0.1, 0.2], embedding_model="prov:model", org_id=5)

    where = coll.query.call_args.kwargs["where"]
    # embedding_model + org_id must be combined with $and
    assert "$and" in where
    assert {"org_id": 5} in where["$and"]
    assert {"embedding_model": "prov:model"} in where["$and"]


def test_vector_query_global_scope_has_no_org_filter():
    from backend.analytics.vector_store import VectorStoreService

    coll = _fake_collection()
    with patch.object(VectorStoreService, "_get_collection", return_value=coll):
        VectorStoreService.query([0.1, 0.2], embedding_model="prov:model", org_id=None)

    where = coll.query.call_args.kwargs.get("where")
    # Only the embedding_model condition remains; no org filter for super_admin.
    assert where == {"embedding_model": "prov:model"}


def test_vector_query_org_only_filter():
    from backend.analytics.vector_store import VectorStoreService

    coll = _fake_collection()
    with patch.object(VectorStoreService, "_get_collection", return_value=coll):
        VectorStoreService.query([0.1, 0.2], org_id=7)

    where = coll.query.call_args.kwargs.get("where")
    assert where == {"org_id": 7}


# ── ChromaDB indexing stamps org_id ─────────────────────────────────────────

def _fake_adapter():
    adapter = MagicMock()
    adapter.provider_name = "openai"
    adapter.get_embedding.return_value = [0.1, 0.2, 0.3]
    adapter._embedding_model = "text-embedding-3-small"
    adapter._model_name = "gpt-4o-mini"
    return adapter


def _index_entity_obj(*, org_id):
    ent = MagicMock()
    ent.id = 123
    ent.org_id = org_id
    ent.primary_label = "Linked Data"
    ent.attributes_json = '{"abstract": "A long enough abstract about linked data and the semantic web."}'
    ent.normalized_json = "{}"
    ent.enrichment_doi = "10.1/x"
    ent.canonical_id = "10.1/x"
    ent.enrichment_concepts = "linked data, semantic web"
    ent.enrichment_citation_count = 10
    ent.enrichment_source = "wos"
    ent.entity_type = "paper"
    ent.secondary_label = "Doe, J"
    return ent


def test_index_entity_stamps_org_id_in_metadata():
    from backend.analytics import rag_engine

    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)

    with patch.object(rag_engine, "_build_adapter", return_value=_fake_adapter()), \
         patch.object(rag_engine.VectorStoreService, "upsert_document", side_effect=_capture):
        rag_engine.index_entity(_index_entity_obj(org_id=42), integration_record=MagicMock())

    assert captured["metadata"]["org_id"] == 42


def test_index_entity_legacy_global_sentinel():
    from backend.analytics import rag_engine
    from backend.tenant_access import LEGACY_GLOBAL_ORG_ID

    captured = {}

    with patch.object(rag_engine, "_build_adapter", return_value=_fake_adapter()), \
         patch.object(rag_engine.VectorStoreService, "upsert_document",
                      side_effect=lambda **kw: captured.update(kw)):
        rag_engine.index_entity(_index_entity_obj(org_id=None), integration_record=MagicMock())

    # org_id None (legacy-global entity) is stored as the -1 sentinel.
    assert captured["metadata"]["org_id"] == LEGACY_GLOBAL_ORG_ID
