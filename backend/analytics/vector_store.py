"""
Phase 5: ChromaDB Vector Store Service
Central point of truth for all embedding indexing and semantic retrieval.
Uses persistent ChromaDB (local disk) with a 'catalog_documents' collection.
"""
import os
from typing import List, Dict, Any, Optional

# Persistent storage for the vector database
CHROMADB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "chromadb")

class VectorStoreService:
    _client = None
    _collection = None
    COLLECTION_NAME = "catalog_documents"

    @classmethod
    def _get_collection(cls):
        if cls._collection is None:
            try:
                import chromadb as _chromadb
            except ImportError as exc:
                raise RuntimeError(
                    "chromadb is not installed. Run: pip install chromadb"
                ) from exc
            os.makedirs(CHROMADB_PATH, exist_ok=True)
            cls._client = _chromadb.PersistentClient(path=CHROMADB_PATH)
            cls._collection = cls._client.get_or_create_collection(
                name=cls.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return cls._collection

    @classmethod
    def upsert_document(cls, doc_id: str, text: str, embedding: List[float], metadata: Dict[str, Any] = {}):
        """Store or update a document embedding in ChromaDB."""
        collection = cls._get_collection()
        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata]
        )

    @classmethod
    def query(
        cls,
        query_embedding: List[float],
        top_k: int = 5,
        min_similarity: float = 0.0,
        embedding_model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the top_k most semantically relevant documents given a query vector.
        Returns list of dicts with 'text', 'id', and 'metadata'.
        """
        collection = cls._get_collection()
        count = collection.count()
        if count == 0:
            return []

        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, count),
            "include": ["documents", "metadatas", "distances"],
        }
        if embedding_model:
            query_kwargs["where"] = {"embedding_model": embedding_model}

        results = collection.query(**query_kwargs)

        docs = []
        for i, doc in enumerate(results["documents"][0]):
            similarity_score = round(1 - results["distances"][0][i], 4)
            if similarity_score < min_similarity:
                continue
            docs.append({
                "id": results["ids"][0][i],
                "text": doc,
                "snippet": doc[:700],
                "metadata": results["metadatas"][0][i],
                "similarity_score": similarity_score
            })
        return docs

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Returns statistics about the current index."""
        collection = cls._get_collection()
        return {
            "total_indexed": collection.count(),
            "collection_name": cls.COLLECTION_NAME,
            "storage_path": CHROMADB_PATH
        }

    @classmethod
    def delete_document(cls, doc_id: str):
        """Remove a document from the index."""
        cls._get_collection().delete(ids=[doc_id])

    @classmethod
    def clear_all(cls):
        """Wipe the entire vector index (use with caution)."""
        if cls._client:
            cls._client.delete_collection(cls.COLLECTION_NAME)
            cls._collection = None
