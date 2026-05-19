"""
Phase 5: RAG Engine — Orchestration Layer
Coordinates the full Retrieval-Augmented Generation pipeline:
  1. Load the active AI provider from the database (BYOK)
  2. Build a LLM adapter instance dynamically
  3. Index catalog records into ChromaDB
  4. Query the vector store and generate responses
"""
import logging
import json
from typing import Optional, List, Dict, Any, Iterable, Tuple

from backend.analytics.vector_store import VectorStoreService

logger = logging.getLogger(__name__)

# System prompt that grounds the LLM strictly in catalog data
SYSTEM_PROMPT = """You are a specialized research assistant for UKIP (Universal Knowledge Intelligence Platform).
Your knowledge comes EXCLUSIVELY from the provided context extracted from the catalog.
Answer questions directly based on the catalog entries, citations, and concepts shown in the context.
If the context doesn't contain enough information to answer confidently, say so transparently.
Be concise, structured, and factual. Respond in the same language used in the question.
"""

MIN_SIMILARITY_SCORE = 0.35
ENRICHED_STATUSES = ("completed", "done", "enriched")


def _build_adapter(integration_record) -> Optional[object]:
    """
    Factory function — reads the active AIIntegration record and returns
    the correct concrete LLM adapter instance.
    """
    if not integration_record:
        return None

    provider = integration_record.provider_name
    api_key = integration_record.api_key or ""
    base_url = integration_record.base_url or ""
    model_name = integration_record.model_name or ""

    try:
        if provider == "openai":
            from backend.adapters.llm.openai_adapter import OpenAIAdapter
            return OpenAIAdapter(api_key=api_key, model_name=model_name or "gpt-4o-mini")

        elif provider == "anthropic":
            from backend.adapters.llm.anthropic_adapter import AnthropicAdapter
            return AnthropicAdapter(api_key=api_key, model_name=model_name or "claude-3-5-haiku-latest")

        elif provider in ("deepseek", "xai", "google", "local"):
            from backend.adapters.llm.local_adapter import LocalAdapter

            BASE_URLS = {
                "deepseek": "https://api.deepseek.com",
                "xai": "https://api.x.ai/v1",
                "google": "https://generativelanguage.googleapis.com/v1beta/openai",
            }
            DEFAULT_MODELS = {
                "deepseek": "deepseek-chat",
                "xai": "grok-3-mini",
                "google": "gemini-2.0-flash",
                "local": "llama3",
            }
            resolved_base_url = base_url if provider == "local" else BASE_URLS.get(provider, base_url)
            resolved_model = model_name or DEFAULT_MODELS.get(provider, "")
            return LocalAdapter(base_url=resolved_base_url, api_key=api_key, model_name=resolved_model)

        else:
            logger.warning(f"UKIP RAGEngine: Unknown provider '{provider}'")
            return None

    except Exception as e:
        logger.error(f"UKIP RAGEngine: Failed to build adapter for '{provider}': {e}")
        return None


def _parse_json_object(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            if items:
                return ", ".join(items)
    return ""


def _read_nested_text(attrs: Dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = attrs.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
        if isinstance(value, list) and value:
            return ", ".join(str(item).strip() for item in value if str(item).strip())
    raw_record = attrs.get("raw_record")
    if isinstance(raw_record, dict):
        return _read_nested_text(raw_record, keys)
    return ""


def _embedding_signature(adapter: object) -> str:
    provider = getattr(adapter, "provider_name", "unknown")
    model = getattr(adapter, "_embedding_model", None) or getattr(adapter, "_model_name", "unknown")
    return f"{provider}:{model}"


def build_entity_rag_document(entity) -> Tuple[str, Dict[str, Any]]:
    """Build the canonical RAG document and metadata for one entity."""
    source_attrs = _parse_json_object(getattr(entity, "attributes_json", None))
    normalized_attrs = _parse_json_object(getattr(entity, "normalized_json", None))
    attrs = {**source_attrs, **normalized_attrs}

    abstract = _read_nested_text(attrs, ("abstract", "abstract_text", "summary", "resumen", "description", "raw_ab", "raw_abstract"))
    doi = _first_text(getattr(entity, "enrichment_doi", None), getattr(entity, "canonical_id", None), attrs.get("doi"), attrs.get("raw_di"))
    journal = _first_text(attrs.get("journal"), attrs.get("venue"), attrs.get("source_title"), attrs.get("raw_so"))
    year = _first_text(attrs.get("year"), attrs.get("publication_year"), attrs.get("raw_py"))
    authors = _first_text(attrs.get("authors"), attrs.get("full_authors"), attrs.get("enrichment_authors"), attrs.get("raw_au"), attrs.get("raw_af"), getattr(entity, "secondary_label", None))
    document_type = _first_text(attrs.get("document_type"), attrs.get("type"), attrs.get("raw_dt"), getattr(entity, "entity_type", None))
    keywords = _first_text(
        getattr(entity, "enrichment_concepts", None),
        attrs.get("keywords"),
        attrs.get("concepts"),
        attrs.get("normalized_keywords"),
    )

    fields = [
        ("Title", getattr(entity, "primary_label", None) or attrs.get("title") or attrs.get("name")),
        ("Authors", authors),
        ("Document Type", document_type),
        ("DOI", doi),
        ("Journal", journal),
        ("Year", year),
        ("Keywords", keywords),
        ("Abstract", abstract),
        ("Citation Count", getattr(entity, "enrichment_citation_count", None) or 0),
        ("Source API", getattr(entity, "enrichment_source", None) or attrs.get("source_name") or attrs.get("source")),
    ]
    text = "\n".join(f"{label}: {value}" for label, value in fields if value not in (None, ""))
    metadata = {
        "entity_id": entity.id,
        "entity_name": getattr(entity, "primary_label", None) or "",
        "doi": doi,
        "journal": journal,
        "year": year,
        "authors": authors,
        "document_type": document_type,
        "keywords": keywords,
        "abstract_preview": abstract[:500],
        "citation_count": getattr(entity, "enrichment_citation_count", None) or 0,
        "source": getattr(entity, "enrichment_source", None) or "unknown",
    }
    return text, metadata


def index_entity(entity, integration_record) -> Dict[str, Any]:
    """
    Phase 5 / Indexing Step:
    Converts an entity's enrichment data into an embedding and stores it in ChromaDB.
    """
    adapter = _build_adapter(integration_record)
    if not adapter:
        return {"status": "error", "message": "No active AI provider configured."}

    text, metadata = build_entity_rag_document(entity)

    if not text.strip() or len(text) < 20:
        return {"status": "skipped", "message": "Insufficient data for indexing."}

    try:
        embedding = adapter.get_embedding(text)
        embedding_signature = _embedding_signature(adapter)
        doc_id = f"entity-{entity.id}"

        VectorStoreService.upsert_document(
            doc_id=doc_id,
            text=text,
            embedding=embedding,
            metadata={
                **metadata,
                "provider_used": adapter.provider_name,
                "embedding_model": embedding_signature,
            }
        )
        return {"status": "indexed", "doc_id": doc_id, "provider": adapter.provider_name, "embedding_model": embedding_signature}
    except Exception as e:
        logger.error(f"RAGEngine index error for entity {entity.id}: {e}")
        return {"status": "error", "message": str(e)}


def query_catalog(
    user_question: str,
    integration_record,
    top_k: int = 5,
    extra_system_context: Optional[str] = None,
    min_similarity: float = MIN_SIMILARITY_SCORE,
) -> Dict[str, Any]:
    """
    Phase 5 / 11 — Generation Step:
    1. Embed the user's question
    2. Retrieve the most relevant catalog documents
    3. Send to LLM for grounded, context-aware generation

    When extra_system_context is provided (Phase 11), it is prepended to the
    system prompt so the model is aware of the current domain state.
    """
    adapter = _build_adapter(integration_record)
    if not adapter:
        return {"error": "No active AI provider configured. Please set an active provider in Integrations → AI Language Models."}

    try:
        # Step 1: Embed user query
        query_embedding = adapter.get_embedding(user_question)

        # Step 2: Retrieve relevant context
        embedding_signature = _embedding_signature(adapter)
        retrieved_docs = VectorStoreService.query(
            query_embedding,
            top_k=top_k,
            min_similarity=min_similarity,
            embedding_model=embedding_signature,
        )

        if not retrieved_docs:
            return {
                "answer": "No sufficiently relevant catalog sources were found for this question. Try lowering the similarity threshold or rebuilding the index if the catalog was recently enriched.",
                "sources": [],
                "min_similarity": min_similarity,
            }

        context_chunks = [doc["text"] for doc in retrieved_docs]

        # Step 3: Build system prompt, optionally enriched with domain context
        system_prompt = SYSTEM_PROMPT
        if extra_system_context:
            system_prompt = extra_system_context + "\n\n" + SYSTEM_PROMPT

        answer = adapter.chat(
            system_prompt=system_prompt,
            user_query=user_question,
            context_chunks=context_chunks
        )

        return {
            "answer": answer,
            "provider": adapter.provider_name,
            "model": getattr(adapter, "_model_name", "unknown"),
            "sources": retrieved_docs,
            "context_chunks_used": len(context_chunks),
            "min_similarity": min_similarity,
            "embedding_model": embedding_signature,
        }

    except Exception as e:
        logger.error(f"RAGEngine query error: {e}")
        return {"error": str(e)}


def query_catalog_agentic(
    user_question: str,
    integration_record,
    db,
    top_k: int = 5,
    extra_system_context: Optional[str] = None,
    max_iterations: int = 5,
    min_similarity: float = MIN_SIMILARITY_SCORE,
) -> Dict[str, Any]:
    """
    Sprint 69C — Agentic RAG with function calling.
    Same as query_catalog() but calls chat_with_tools() so the LLM can
    autonomously invoke tool-registry functions mid-reasoning.
    """
    from backend.tool_registry import get_registry

    adapter = _build_adapter(integration_record)
    if not adapter:
        return {"error": "No active AI provider configured."}

    try:
        query_embedding = adapter.get_embedding(user_question)
        embedding_signature = _embedding_signature(adapter)
        retrieved_docs = VectorStoreService.query(
            query_embedding,
            top_k=top_k,
            min_similarity=min_similarity,
            embedding_model=embedding_signature,
        )

        if not retrieved_docs:
            return {
                "answer": "No sufficiently relevant catalog sources were found for this question. Try lowering the similarity threshold or rebuilding the index if the catalog was recently enriched.",
                "sources": [],
                "tools_used": [],
                "iterations": 0,
                "agentic": True,
                "min_similarity": min_similarity,
            }

        context_chunks = [doc["text"] for doc in retrieved_docs]

        system_prompt = SYSTEM_PROMPT
        if extra_system_context:
            system_prompt = extra_system_context + "\n\n" + SYSTEM_PROMPT

        registry = get_registry()
        tools = registry.list_tools()

        def _invoke(name: str, params: Dict[str, Any]) -> Any:
            return registry.invoke(name, params, db)

        agentic_result = adapter.chat_with_tools(
            system_prompt=system_prompt,
            user_query=user_question,
            context_chunks=context_chunks,
            tools=tools,
            tool_invoker=_invoke,
            max_iterations=max_iterations,
        )

        return {
            "answer":               agentic_result["answer"],
            "provider":             adapter.provider_name,
            "model":                getattr(adapter, "_model_name", "unknown"),
            "sources":              retrieved_docs,
            "context_chunks_used":  len(context_chunks),
            "tools_used":           agentic_result["tools_used"],
            "iterations":           agentic_result["iterations"],
            "agentic":              True,
            "min_similarity":        min_similarity,
            "embedding_model":       embedding_signature,
        }

    except Exception as e:
        logger.error(f"RAGEngine agentic query error: {e}")
        return {"error": str(e)}
