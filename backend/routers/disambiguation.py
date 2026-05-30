"""
Disambiguation and normalization rules endpoints.
  GET  /disambiguate/{field}
  POST /disambiguate/ai-resolve
  GET  /rules
  POST /rules/bulk
  DELETE /rules/{rule_id}
  POST /rules/apply
"""
import json
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import update
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.services.engine_delegation import (
    ENGINE_DELEGATION_THRESHOLD,
    _get_engine_client,
    try_engine_disambiguation,
    try_engine_normalization,
)
from backend.tenant_access import (
    get_scoped_record,
    org_scope_filter,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)
from backend.llm_agent import resolve_canonical_name
from backend.routers.deps import _build_disambig_groups
from backend.routers.limiter import limiter
from backend.services.entity_query import entity_base_q

logger = logging.getLogger(__name__)

router = APIRouter(tags=["disambiguation"])


# ── Disambiguation ────────────────────────────────────────────────────────────

@router.get("/disambiguate/{field}")
async def disambiguate_field(
    request: Request,
    response: Response,
    field: str,
    threshold: int = Query(default=80, ge=0, le=100),
    algorithm: str = Query(default="token_sort", pattern="^(token_sort|fingerprint|ngram|phonetic)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        # Count unique values to decide delegation
        org_id = resolve_request_org_id(db, current_user)
        engine_client = _get_engine_client(request)
        if engine_client is not None:
            # Quick count check — extract values for engine
            from backend.routers.deps import _FIELD_RE
            from sqlalchemy import func as sqla_func
            if _FIELD_RE.match(field) and hasattr(models.RawEntity, field):
                column = getattr(models.RawEntity, field)
                unique_count = (
                    entity_base_q(db, "all", org_id)
                    .with_entities(sqla_func.count(sqla_func.distinct(column)))
                    .filter(column != None)
                    .scalar()
                ) or 0
                if unique_count > ENGINE_DELEGATION_THRESHOLD:
                    # Extract values for engine
                    vals_q = (
                        entity_base_q(db, "all", org_id)
                        .with_entities(column)
                        .distinct()
                        .filter(column != None)
                    )
                    values = [v[0] for v in vals_q.all() if v[0] and str(v[0]).strip()]
                    engine_groups = await try_engine_disambiguation(
                        engine_client, field, values, threshold,
                        similarity_threshold=threshold / 100,
                    )
                    if engine_groups is not None:
                        total = len(engine_groups)
                        page = engine_groups[skip : skip + limit]
                        response.headers["X-Total-Count"] = str(total)
                        return {"groups": page, "total_groups": total, "algorithm": "engine"}

        groups, total = _build_disambig_groups(
            field, threshold, db, algorithm=algorithm, org_id=org_id,
            skip=skip, limit=limit, with_total=True,
        )
        response.headers["X-Total-Count"] = str(total)
        return {"groups": groups, "total_groups": total, "algorithm": algorithm}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class AIResolveRequest(BaseModel):
    field_name: str = PydanticField(..., min_length=1, max_length=200)
    variations: List[str]


@router.post("/disambiguate/ai-resolve")
@limiter.limit("10/minute")
def ai_resolve_variations(
    request: Request,
    payload: AIResolveRequest,
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Sends a cluster of lexical variations to the LLM agent to figure out the canonical name
    and provide ontological reasoning.
    """
    try:
        resolution = resolve_canonical_name(
            field_name=payload.field_name,
            variations=payload.variations,
        )
        return resolution
    except Exception:
        logger.exception("LLM AI-resolve error for field '%s'", payload.field_name)
        raise HTTPException(
            status_code=500,
            detail="AI resolution failed. Check server logs for details.",
        )


# ── Normalization Rules ───────────────────────────────────────────────────────

@router.get("/rules", response_model=List[schemas.Rule])
def get_rules(
    field_name: str = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    query = scope_query_to_org(db.query(models.NormalizationRule), models.NormalizationRule, org_id)
    if field_name:
        query = query.filter(models.NormalizationRule.field_name == field_name)
    return query.order_by(models.NormalizationRule.id.desc()).offset(skip).limit(limit).all()


@router.post("/rules/bulk", status_code=201)
def create_rules_bulk(
    payload: schemas.BulkRuleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    rule_org_id = persisted_org_id(org_id)
    for var in payload.variations:
        if var == payload.canonical_value:
            continue
        existing = scope_query_to_org(
            db.query(models.NormalizationRule), models.NormalizationRule, org_id
        ).filter(
            models.NormalizationRule.field_name == payload.field_name,
            models.NormalizationRule.original_value == var,
        ).first()
        if existing:
            existing.normalized_value = payload.canonical_value
        else:
            db.add(models.NormalizationRule(
                org_id=rule_org_id,
                field_name=payload.field_name,
                original_value=var,
                canonical_value=payload.canonical_value,
                rule_type="exact",
            ))
    db.commit()
    return {
        "message": f"Rules saved for '{payload.canonical_value}'",
        "variations": len(payload.variations) - 1,
    }


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    rule = get_scoped_record(db, models.NormalizationRule, rule_id, org_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"message": "Rule deleted"}


@router.post("/rules/apply")
async def apply_rules(
    request: Request,
    field_name: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    query = scope_query_to_org(db.query(models.NormalizationRule), models.NormalizationRule, org_id)
    if field_name:
        query = query.filter(models.NormalizationRule.field_name == field_name)
    rules = query.all()

    # Separate exact-match and regex rules
    exact_rules = [r for r in rules if not r.is_regex]
    regex_rules = [r for r in rules if r.is_regex]

    total_updated = 0

    # Try engine delegation for bulk exact-match rules
    if exact_rules and len(exact_rules) > ENGINE_DELEGATION_THRESHOLD:
        engine_client = _get_engine_client(request)
        if engine_client is not None:
            # Collect unique values that need normalization
            values_to_normalize = [r.original_value for r in exact_rules]
            engine_rules = [
                {"pattern": r.original_value, "replacement": r.normalized_value}
                for r in exact_rules
            ]
            mapping = await try_engine_normalization(
                engine_client,
                field_name=field_name or "mixed",
                values=values_to_normalize,
                mode="rules",
                rules=engine_rules,
            )
            if mapping is not None:
                # Apply the mapping via bulk SQL updates
                for original, normalized in mapping.items():
                    for rule in exact_rules:
                        if rule.original_value == original and hasattr(models.RawEntity, rule.field_name):
                            column = getattr(models.RawEntity, rule.field_name)
                            filters = [column == original]
                            org_filter = org_scope_filter(models.RawEntity.org_id, org_id)
                            if org_filter is not None:
                                filters.append(org_filter)
                            result = db.execute(
                                update(models.RawEntity)
                                .where(*filters)
                                .values({rule.field_name: normalized})
                            )
                            total_updated += result.rowcount
                # Only process regex rules in the Python path
                rules = regex_rules
                if not rules:
                    db.commit()
                    return {
                        "message": f"Applied {len(exact_rules)} rules (engine) + {len(regex_rules)} rules (python)",
                        "rules_applied": len(exact_rules) + len(regex_rules),
                        "records_updated": total_updated,
                    }

    for rule in rules:
        if hasattr(models.RawEntity, rule.field_name):
            column = getattr(models.RawEntity, rule.field_name)
            if rule.is_regex:
                entities = (
                    entity_base_q(db, "all", org_id)
                    .filter(column != None)
                    .all()
                )
                for p in entities:
                    original = getattr(p, rule.field_name)
                    if original:
                        try:
                            new_val = re.sub(rule.original_value, rule.normalized_value, original)
                            if new_val != original:
                                setattr(p, rule.field_name, new_val)
                                total_updated += 1
                        except re.error:
                            pass
            else:
                filters = [column == rule.original_value]
                org_filter = org_scope_filter(models.RawEntity.org_id, org_id)
                if org_filter is not None:
                    filters.append(org_filter)
                result = db.execute(
                    update(models.RawEntity)
                    .where(*filters)
                    .values({rule.field_name: rule.normalized_value})
                )
                total_updated += result.rowcount
        else:
            entities = (
                entity_base_q(db, "all", org_id)
                .filter(models.RawEntity.normalized_json != None)
                .all()
            )
            for entity in entities:
                try:
                    data = json.loads(entity.normalized_json or "{}")
                    original = data.get(rule.field_name)
                    if original:
                        if rule.is_regex:
                            new_val = re.sub(rule.original_value, rule.normalized_value, original)
                        else:
                            new_val = (
                                rule.normalized_value
                                if original == rule.original_value
                                else original
                            )
                        if new_val != original:
                            data[rule.field_name] = new_val
                            entity.normalized_json = json.dumps(data)
                            db.add(entity)
                            total_updated += 1
                except Exception as exc:
                    logger.warning(
                        "Rule application skipped for entity %s: %s", entity.id, exc
                    )
                    continue

    db.commit()
    return {
        "message": f"Applied {len(rules)} rules",
        "rules_applied": len(rules),
        "records_updated": total_updated,
    }
