from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.analytics import rag_engine
from backend.analytics.vector_store import VectorStoreService


def test_build_entity_rag_document_includes_abstract_and_academic_metadata():
    entity = SimpleNamespace(
        id=7,
        primary_label="Knowledge Graph Mining",
        secondary_label="Ada Lovelace",
        entity_type="article",
        canonical_id="10.1234/kg",
        attributes_json='{"journal":"AI Review","year":2024,"abstract":"Pattern discovery over graph corpora.","keywords":["graphs","patterns"]}',
        normalized_json='{"document_type":"Research Article"}',
        enrichment_doi="10.1234/kg",
        enrichment_citation_count=12,
        enrichment_concepts="graph mining, pattern analysis",
        enrichment_source="openalex",
    )

    text, metadata = rag_engine.build_entity_rag_document(entity)

    assert "Abstract: Pattern discovery over graph corpora." in text
    assert "DOI: 10.1234/kg" in text
    assert "Journal: AI Review" in text
    assert "Year: 2024" in text
    assert "Authors: Ada Lovelace" in text
    assert "Keywords: graph mining, pattern analysis" in text
    assert metadata["abstract_preview"] == "Pattern discovery over graph corpora."
    assert metadata["doi"] == "10.1234/kg"


def test_index_entity_stores_embedding_model_metadata():
    entity = SimpleNamespace(
        id=8,
        primary_label="Semantic Search",
        secondary_label=None,
        entity_type="paper",
        canonical_id=None,
        attributes_json="{}",
        normalized_json=None,
        enrichment_doi=None,
        enrichment_citation_count=0,
        enrichment_concepts="semantic retrieval",
        enrichment_source="openalex",
    )
    adapter = MagicMock()
    adapter.provider_name = "openai"
    adapter._embedding_model = "text-embedding-3-small"
    adapter.get_embedding.return_value = [0.1, 0.2]

    with patch("backend.analytics.rag_engine._build_adapter", return_value=adapter), \
         patch("backend.analytics.rag_engine.VectorStoreService.upsert_document") as upsert:
        result = rag_engine.index_entity(entity, MagicMock())

    assert result["status"] == "indexed"
    metadata = upsert.call_args.kwargs["metadata"]
    assert metadata["embedding_model"] == "openai:text-embedding-3-small"


def test_vector_query_filters_by_similarity_and_embedding_model():
    collection = MagicMock()
    collection.count.return_value = 2
    collection.query.return_value = {
        "documents": [["Strong match", "Weak match"]],
        "ids": [["entity-1", "entity-2"]],
        "metadatas": [[{"embedding_model": "openai:text-embedding-3-small"}, {"embedding_model": "openai:text-embedding-3-small"}]],
        "distances": [[0.1, 0.8]],
    }

    with patch.object(VectorStoreService, "_get_collection", return_value=collection):
        docs = VectorStoreService.query(
            [0.1, 0.2],
            top_k=2,
            min_similarity=0.35,
            embedding_model="openai:text-embedding-3-small",
        )

    collection.query.assert_called_once()
    assert collection.query.call_args.kwargs["where"] == {"embedding_model": "openai:text-embedding-3-small"}
    assert [doc["id"] for doc in docs] == ["entity-1"]
    assert docs[0]["snippet"] == "Strong match"
