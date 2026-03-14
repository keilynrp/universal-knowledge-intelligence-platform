"""
Natural Language Query (NLQ) router.

Translates free-text questions into OLAP cube queries using the active
AI integration, then executes the query and returns both the translated
parameters and the raw results.

POST /nlq/query
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user
from backend.database import get_db
from backend.encryption import decrypt
from backend.olap import olap_engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["nlq"])

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_active_integration(db: Session):
    """Return the decrypted active AIIntegration, or None."""
    integration = (
        db.query(models.AIIntegration)
        .filter(models.AIIntegration.is_active == True)  # noqa: E712
        .first()
    )
    if not integration:
        return None
    db.expunge(integration)          # detach before decrypting
    if integration.api_key:
        integration.api_key = decrypt(integration.api_key)
    return integration


def _build_system_prompt(dimensions: list[dict]) -> str:
    dims_block = "\n".join(
        f'  - "{d["name"]}" ({d["type"]}, {d["distinct_count"]} distinct values): {d["label"]}'
        for d in dimensions
    )
    return f"""You are a data analyst assistant that translates natural language questions into OLAP cube queries.

Available dimensions (use ONLY these exact names):
{dims_block}

Respond with ONLY valid JSON — no markdown, no code fences, no extra text:
{{
  "group_by": ["dimension_name_1"],
  "filters": {{}},
  "explanation": "One sentence describing what you are computing."
}}

Rules:
- group_by: list of 1 or 2 dimension names from the list above (exact snake_case names, not labels)
- filters: equality filters as {{dimension_name: "value"}}, or empty dict {{}}
- explanation: concise human-readable sentence describing the query
- NEVER invent dimension names not present in the list above
- If the question mentions a limit (e.g. "top 10"), note it in the explanation — the API always returns results sorted by count descending"""


# ── Schema ────────────────────────────────────────────────────────────────────

class NLQRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    domain_id: str = Field(default="default", min_length=1, max_length=64)


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/nlq/query", dependencies=[Depends(get_current_user)])
async def nlq_query(payload: NLQRequest, db: Session = Depends(get_db)):
    """
    Translate a natural language question into an OLAP query and return results.

    Returns:
        question: the original question
        translated: {group_by, filters, explanation}
        result: the standard CubeResult object
    """
    # 1. Load domain dimensions
    try:
        dimensions = olap_engine.get_dimensions(payload.domain_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("NLQ: failed to load dimensions for domain '%s'", payload.domain_id)
        raise HTTPException(status_code=500, detail=f"Failed to load dimensions: {e}")

    if not dimensions:
        raise HTTPException(
            status_code=400,
            detail="No dimensions available for this domain. Upload data first.",
        )

    # 2. Get active AI integration
    integration = _get_active_integration(db)
    if not integration:
        raise HTTPException(
            status_code=400,
            detail="No active AI provider. Configure one in Integrations → AI Language Models.",
        )

    # 3. Call LLM
    system_prompt = _build_system_prompt(dimensions)
    try:
        from backend.analytics.rag_engine import _build_adapter  # lazy import

        adapter = _build_adapter(integration)
        if adapter is None:
            raise HTTPException(
                status_code=400,
                detail="Could not build LLM adapter for the configured provider.",
            )

        raw = adapter.chat(
            system_prompt=system_prompt,
            user_query=payload.question,
            context_chunks=[],
        )

        # Strip markdown code fences if LLM added them
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        translated = json.loads(raw)

    except json.JSONDecodeError:
        logger.warning("NLQ: LLM returned non-JSON: %s", raw[:200] if "raw" in dir() else "?")
        raise HTTPException(
            status_code=422,
            detail="The AI returned an invalid response. Try rephrasing your question.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("NLQ: LLM call failed")
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

    # 4. Validate & sanitise LLM output
    valid_dim_names = {d["name"] for d in dimensions}
    group_by: list[str] = [
        g for g in (translated.get("group_by") or []) if g in valid_dim_names
    ]
    if not group_by:
        sample = ", ".join(f'"{d["label"]}"' for d in dimensions[:5])
        raise HTTPException(
            status_code=422,
            detail=(
                f"Could not map your question to the available data dimensions. "
                f"Try mentioning one of: {sample}."
            ),
        )

    filters: dict[str, str] = {
        k: str(v)
        for k, v in (translated.get("filters") or {}).items()
        if k in valid_dim_names and v is not None
    }
    explanation: str = translated.get("explanation", "")

    # 5. Execute OLAP query
    try:
        result = olap_engine.query_cube(
            domain_id=payload.domain_id,
            group_by=group_by,
            filters=filters or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("NLQ: OLAP query failed")
        raise HTTPException(status_code=500, detail=f"OLAP query failed: {e}")

    return {
        "question": payload.question,
        "translated": {
            "group_by": group_by,
            "filters": filters,
            "explanation": explanation,
        },
        "result": result,
    }
