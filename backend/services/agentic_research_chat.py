from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.analytics import rag_engine
from backend.context_engine import ContextEngine
from backend.olap import olap_engine
from backend.routers.deps import _get_active_integration
from backend.routers.nlq import NLQSanitizer, _build_system_prompt
from backend.services.pattern_discovery import PatternDiscoveryService
from backend.tenant_access import persisted_org_id, scope_query_to_org

logger = logging.getLogger(__name__)

ChatMode = Literal["auto", "rag", "nlq", "hybrid"]


class AgenticChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=5000)
    mode: ChatMode = "auto"
    domain_id: str = Field(default="default", min_length=1, max_length=64)
    import_batch_id: int | None = Field(default=None, ge=1)
    provider: str | None = Field(default=None, max_length=80)
    portal_slug: str | None = Field(default=None, max_length=160)
    entity_id: int | None = Field(default=None, ge=1)
    top_k: int = Field(default=6, ge=1, le=20)
    use_tools: bool = True
    persist_trace: bool = True


class AgenticResearchChatService:
    """Orchestrates NLQ, RAG, structured context and trace persistence."""

    @classmethod
    def ask(
        cls,
        db: Session,
        payload: AgenticChatRequest,
        current_user: models.User,
        org_id: int | None,
    ) -> dict[str, Any]:
        mode_used = cls._resolve_mode(payload.question, payload.mode)
        scope = cls._scope_payload(payload)
        context = cls._build_context_blocks(db, payload, org_id)
        integration = _get_active_integration(db)

        rag_result: dict[str, Any] | None = None
        nlq_result: dict[str, Any] | None = None
        errors: list[str] = []

        if mode_used in {"rag", "hybrid"}:
            rag_result = cls._run_rag(db, payload, integration, context["system_prompt"], org_id)
            if rag_result.get("error"):
                errors.append(str(rag_result["error"]))

        if mode_used in {"nlq", "hybrid"}:
            nlq_result = cls._run_nlq(db, payload, integration)
            if nlq_result.get("error"):
                errors.append(str(nlq_result["error"]))

        answer = cls._compose_answer(
            payload=payload,
            mode_used=mode_used,
            rag_result=rag_result,
            nlq_result=nlq_result,
            context=context,
            errors=errors,
        )
        sources = cls._normalize_sources(rag_result)
        trace = cls._build_trace(
            payload=payload,
            mode_used=mode_used,
            rag_result=rag_result,
            nlq_result=nlq_result,
            context=context,
            integration=integration,
            errors=errors,
        )

        trace_id = None
        if payload.persist_trace:
            trace_id = cls._persist_trace(
                db=db,
                payload=payload,
                answer=answer,
                sources=sources,
                trace=trace,
                current_user=current_user,
                org_id=org_id,
            )

        return {
            "answer": answer,
            "mode_used": mode_used,
            "scope": scope,
            "trace_id": trace_id,
            "trace": trace,
            "sources": sources,
            "follow_up_questions": cls._follow_ups(payload, mode_used),
        }

    @staticmethod
    def _scope_payload(payload: AgenticChatRequest) -> dict[str, Any]:
        return {
            "domain_id": payload.domain_id,
            "import_batch_id": payload.import_batch_id,
            "provider": payload.provider,
            "portal_slug": payload.portal_slug,
            "entity_id": payload.entity_id,
        }

    @staticmethod
    def _resolve_mode(question: str, requested_mode: ChatMode) -> Literal["rag", "nlq", "hybrid"]:
        if requested_mode != "auto":
            return "hybrid" if requested_mode == "hybrid" else requested_mode

        q = question.lower()
        aggregate_intent = re.search(
            r"\b(cuant|cu[aá]nt|distribuci[oó]n|porcentaje|tasa|promedio|top|ranking|por dominio|por proveedor)\b",
            q,
        )
        evidence_intent = re.search(
            r"\b(evidencia|fuente|registro|paper|articulo|cuales|cu[aá]les|por qu[eé]|explica)\b",
            q,
        )
        exploration_intent = re.search(
            r"\b(patron|patr[oó]n|brecha|riesgo|impacto|recomendaci[oó]n|stakeholder|brief)\b",
            q,
        )
        if aggregate_intent and (evidence_intent or exploration_intent):
            return "hybrid"
        if aggregate_intent:
            return "nlq"
        return "hybrid" if exploration_intent else "rag"

    @classmethod
    def _build_context_blocks(
        cls,
        db: Session,
        payload: AgenticChatRequest,
        org_id: int | None,
    ) -> dict[str, Any]:
        blocks: dict[str, Any] = {}

        try:
            ctx = ContextEngine().build_domain_context(payload.domain_id, db, org_id)
            blocks["domain_snapshot"] = ctx
        except Exception as exc:
            blocks["domain_snapshot_error"] = str(exc)

        entity = None
        if payload.entity_id:
            entity = (
                scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
                .filter(models.RawEntity.id == payload.entity_id)
                .first()
            )
            if entity:
                blocks["entity_profile"] = cls._entity_profile(entity)
            else:
                blocks["entity_profile_error"] = f"Entity {payload.entity_id} not found in scope."

        try:
            blocks["hidden_patterns"] = PatternDiscoveryService.discover(
                db,
                domain_id=payload.domain_id,
                org_id=org_id,
                import_batch_id=payload.import_batch_id,
                provider=payload.provider,
                portal_slug=payload.portal_slug,
                limit=4,
            )
        except Exception as exc:
            blocks["hidden_patterns_error"] = str(exc)

        summary = cls._scope_summary(db, payload, org_id)
        blocks["scope_summary"] = summary

        system_prompt = (
            "UKIP structured context for this answer. Respect the declared scope, "
            "avoid inventing missing metadata, and cite catalog sources when available.\n"
            + json.dumps(blocks, ensure_ascii=False, default=str)[:12000]
        )
        return {"blocks": blocks, "system_prompt": system_prompt}

    @staticmethod
    def _scope_summary(db: Session, payload: AgenticChatRequest, org_id: int | None) -> dict[str, Any]:
        query = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).filter(
            models.RawEntity.domain == payload.domain_id
        )
        if payload.import_batch_id:
            query = query.filter(models.RawEntity.import_batch_id == payload.import_batch_id)
        if payload.provider:
            query = query.filter(
                (models.RawEntity.enrichment_source == payload.provider)
                | (models.RawEntity.source == payload.provider)
            )
        total = query.with_entities(func.count(models.RawEntity.id)).scalar() or 0
        enriched = query.filter(
            models.RawEntity.enrichment_status.in_(["completed", "done", "enriched"])
        ).with_entities(func.count(models.RawEntity.id)).scalar() or 0
        avg_quality = query.with_entities(func.avg(models.RawEntity.quality_score)).scalar()
        return {
            "records": int(total),
            "enriched": int(enriched),
            "enrichment_pct": round(enriched / total * 100, 1) if total else 0.0,
            "avg_quality": round(float(avg_quality), 3) if avg_quality is not None else None,
        }

    @staticmethod
    def _entity_profile(entity: models.RawEntity) -> dict[str, Any]:
        return {
            "id": entity.id,
            "label": entity.primary_label,
            "canonical_id": entity.canonical_id,
            "entity_type": entity.entity_type,
            "domain": entity.domain,
            "source": entity.source,
            "enrichment_source": entity.enrichment_source,
            "enrichment_status": entity.enrichment_status,
            "citations": entity.enrichment_citation_count,
            "concepts": entity.enrichment_concepts,
            "quality_score": entity.quality_score,
        }

    @staticmethod
    def _run_rag(
        db: Session,
        payload: AgenticChatRequest,
        integration,
        extra_system_context: str,
        org_id: int | None,
    ) -> dict[str, Any]:
        if payload.use_tools:
            return rag_engine.query_catalog_agentic(
                user_question=payload.question,
                integration_record=integration,
                db=db,
                top_k=payload.top_k,
                extra_system_context=extra_system_context,
                max_iterations=4,
                org_id=org_id,
            )
        return rag_engine.query_catalog(
            user_question=payload.question,
            integration_record=integration,
            top_k=payload.top_k,
            extra_system_context=extra_system_context,
            org_id=org_id,
        )

    @staticmethod
    def _run_nlq(db: Session, payload: AgenticChatRequest, integration) -> dict[str, Any]:
        if not integration:
            return {"error": "No active AI provider configured for NLQ."}
        try:
            dimensions = olap_engine.get_dimensions(payload.domain_id)
            if not dimensions:
                return {"error": "No OLAP dimensions available for this domain."}
            adapter = rag_engine._build_adapter(integration)
            if adapter is None:
                return {"error": "Could not build LLM adapter for NLQ."}
            raw = adapter.chat(
                system_prompt=_build_system_prompt(dimensions),
                user_query=payload.question,
                context_chunks=[],
            ).strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            translated = json.loads(raw.strip())
            valid_dim_names = {d["name"] for d in dimensions}
            group_by, filters = NLQSanitizer.sanitize(translated, valid_dim_names)
            result = olap_engine.query_cube(
                domain_id=payload.domain_id,
                group_by=group_by,
                filters=filters or None,
            )
            return {
                "translated": {
                    "group_by": group_by,
                    "filters": filters,
                    "explanation": translated.get("explanation", ""),
                },
                "result": result,
            }
        except Exception as exc:
            logger.warning("Agentic chat NLQ branch failed: %s", exc)
            return {"error": str(exc)}

    @staticmethod
    def _compose_answer(
        payload: AgenticChatRequest,
        mode_used: str,
        rag_result: dict[str, Any] | None,
        nlq_result: dict[str, Any] | None,
        context: dict[str, Any],
        errors: list[str],
    ) -> str:
        rag_answer = (rag_result or {}).get("answer")
        nlq_translated = (nlq_result or {}).get("translated")
        nlq_result_data = (nlq_result or {}).get("result")
        summary = context["blocks"].get("scope_summary", {})

        parts: list[str] = []
        if rag_answer:
            parts.append(str(rag_answer))
        if nlq_translated and nlq_result_data:
            parts.append(
                "Lectura NLQ: "
                + str(nlq_translated.get("explanation") or "consulta estructurada ejecutada")
                + f". Resultado: {json.dumps(nlq_result_data, ensure_ascii=False, default=str)[:1200]}"
            )
        if parts:
            return "\n\n".join(parts)

        if errors:
            return (
                "No pude completar la consulta con el proveedor LLM activo. "
                "Aun asi, el alcance quedo preparado para analisis: "
                f"{summary.get('records', 0)} registros, "
                f"{summary.get('enrichment_pct', 0)}% enriquecidos. "
                "Configura o revisa el proveedor AI/RAG y vuelve a intentar. "
                f"Detalle tecnico: {'; '.join(errors[:2])}"
            )

        return (
            "El alcance esta listo para consulta, pero no hay suficiente evidencia indexada "
            "para producir una respuesta confiable. Indexa el catalogo RAG o ejecuta enrichment "
            "antes de usar esta pregunta como evidencia de brief."
        )

    @staticmethod
    def _normalize_sources(rag_result: dict[str, Any] | None) -> list[dict[str, Any]]:
        normalized = []
        for doc in (rag_result or {}).get("sources", []) or []:
            metadata = doc.get("metadata") or {}
            normalized.append({
                "entity_id": metadata.get("entity_id") or doc.get("entity_id"),
                "label": metadata.get("entity_name") or doc.get("label") or doc.get("text", "")[:90],
                "score": doc.get("score") or doc.get("distance"),
                "source": metadata.get("source") or "catalog",
            })
        return normalized

    @staticmethod
    def _build_trace(
        payload: AgenticChatRequest,
        mode_used: str,
        rag_result: dict[str, Any] | None,
        nlq_result: dict[str, Any] | None,
        context: dict[str, Any],
        integration,
        errors: list[str],
    ) -> dict[str, Any]:
        return {
            "rag_used": mode_used in {"rag", "hybrid"},
            "nlq_used": mode_used in {"nlq", "hybrid"},
            "tools_used": (rag_result or {}).get("tools_used", []),
            "context_blocks": list(context["blocks"].keys()),
            "iterations": (rag_result or {}).get("iterations", 0),
            "provider": getattr(integration, "provider_name", None),
            "model": getattr(integration, "model_name", None),
            "errors": errors,
        }

    @staticmethod
    def _persist_trace(
        db: Session,
        payload: AgenticChatRequest,
        answer: str,
        sources: list[dict[str, Any]],
        trace: dict[str, Any],
        current_user: models.User,
        org_id: int | None,
    ) -> int:
        snapshot = {
            "kind": "agentic_chat_trace",
            "question": payload.question,
            "answer": answer,
            "scope": AgenticResearchChatService._scope_payload(payload),
            "sources": sources,
            "trace": trace,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        record = models.AnalysisContext(
            domain_id=payload.domain_id,
            user_id=current_user.id,
            org_id=persisted_org_id(org_id),
            label=f"agentic-chat: {payload.question[:72]}",
            context_snapshot=json.dumps(snapshot, ensure_ascii=False, default=str),
            notes="Saved agentic research chat trace.",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return int(record.id)

    @staticmethod
    def _follow_ups(payload: AgenticChatRequest, mode_used: str) -> list[str]:
        if payload.entity_id:
            return [
                "Que evidencia sostiene este registro?",
                "Como se conecta con otros autores, afiliaciones o conceptos?",
                "Conviene incluirlo en el brief final?",
            ]
        if mode_used == "nlq":
            return [
                "Puedes mostrar el mismo resultado por proveedor?",
                "Que dominio concentra mas registros?",
                "Como cambia la distribucion por tipo de entidad?",
            ]
        return [
            "Que registros sostienen mejor esta conclusion?",
            "Que brechas deberia corregir antes del brief?",
            "Como cambia el patron por proveedor o ingesta?",
        ]
