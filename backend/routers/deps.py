"""
Shared dependencies and utility functions used across multiple routers.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import threading
import urllib.request as _urllib_req
from datetime import datetime, timezone

from sqlalchemy import func

from sqlalchemy.orm import Session
from thefuzz import fuzz, process

from backend import database, models
from backend.adapters import get_adapter
from backend.encryption import decrypt
from backend.services.entity_query import entity_base_q
from backend.tenant_access import scope_query_to_org

logger = logging.getLogger(__name__)

# Field-name validation regex (reused by disambiguation and authority routers)
_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _blocking_enabled() -> bool:
    """Whether to use blocking + Union-Find clustering (Phase 2, Task 6).

    Off by default until the evaluation harness (Task 9) validates the switch.
    """
    return os.environ.get("UKIP_USE_BLOCKING", "").strip().lower() in ("1", "true", "yes", "on")


# Audit helper
def _audit(
    db: Session,
    action: str,
    user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict | None = None,
) -> None:
    """Append a row to audit_logs (does not commit; caller must commit)."""
    entry = models.AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        details=json.dumps(details) if details else None,
    )
    db.add(entry)


def _build_disambig_groups(
    field: str,
    threshold: int,
    db: Session,
    algorithm: str = "token_sort",
    org_id: int | None = None,
    skip: int | None = None,
    limit: int | None = None,
    with_total: bool = False,
):
    """
    Shared disambiguation logic.
    algorithm: "token_sort" | "fingerprint" | "ngram" | "phonetic"

    When ``with_total`` is True, returns ``(page, total)`` where ``page`` is the
    ``skip``/``limit`` slice of the full group list and ``total`` is the full
    count. Otherwise returns the full group list (legacy behavior).
    """
    if not _FIELD_RE.match(field):
        raise ValueError(
            f"Invalid field name '{field}'. Must be 1-64 lowercase alphanumeric/underscore "
            "characters starting with a letter."
        )
    if hasattr(models.RawEntity, field):
        column = getattr(models.RawEntity, field)
        query = (
            entity_base_q(db, "all", org_id)
            .with_entities(column)
            .distinct()
            .filter(column != None)
        )
        entries = query.all()
        values = [v[0] for v in entries if v[0] and str(v[0]).strip()]
    else:
        from backend.database import engine as _engine
        if _engine.dialect.name == "postgresql":
            from sqlalchemy import cast
            from sqlalchemy.dialects.postgresql import JSONB
            json_col = cast(models.RawEntity.normalized_json, JSONB)[field].astext
        else:
            json_col = func.json_extract(models.RawEntity.normalized_json, f"$.{field}")
        query = (
            entity_base_q(db, "all", org_id)
            .with_entities(json_col)
            .distinct()
            .filter(
                models.RawEntity.normalized_json != None,
                json_col != None,
            )
        )
        entries = query.all()
        values = [v[0] for v in entries if v[0] and str(v[0]).strip()]

    values.sort(key=len, reverse=True)
    groups = []

    # Blocking + Union-Find path (flagged). Order-independent and transitive;
    # replaces the greedy O(n²) token_sort/ngram loops when UKIP_USE_BLOCKING is on.
    if algorithm in ("token_sort", "ngram") and _blocking_enabled():
        from backend.clustering.blocking import cluster_values
        from backend.clustering.semantic import maybe_build_index

        # Semantic candidates (Task 8) are flag-gated and degrade to None when
        # no embedder is available, leaving pure lexical blocking unchanged.
        semantic_index = maybe_build_index(db, values)
        algo_label = (
            f"{algorithm}+blocking+semantic" if semantic_index else f"{algorithm}+blocking"
        )

        for component in cluster_values(values, threshold, semantic_index=semantic_index):
            if len(component) > 1:
                main = max(component, key=len)
                groups.append({
                    "main": main,
                    "variations": component,
                    "count": len(component),
                    "algorithm_used": algo_label,
                })
        groups.sort(key=lambda g: g["count"], reverse=True)
        if with_total:
            total = len(groups)
            start = skip or 0
            page = groups[start : start + limit] if limit is not None else groups[start:]
            return page, total
        return groups

    if algorithm == "token_sort":
        processed = set()
        for val in values:
            if val in processed:
                continue
            matches = process.extract(val, values, scorer=fuzz.token_sort_ratio, limit=50)
            group_members = [m[0] for m in matches if m[1] >= threshold]
            if len(group_members) > 1:
                groups.append({
                    "main": val,
                    "variations": group_members,
                    "count": len(group_members),
                    "algorithm_used": "token_sort",
                })
                for member in group_members:
                    processed.add(member)
            else:
                processed.add(val)

    elif algorithm == "fingerprint":
        from backend.clustering.algorithms import fingerprint as _fp

        buckets: dict = {}
        for val in values:
            key = _fp(val)
            if key:
                buckets.setdefault(key, []).append(val)
        for members in buckets.values():
            if len(members) > 1:
                main = max(members, key=len)
                groups.append({
                    "main": main,
                    "variations": members,
                    "count": len(members),
                    "algorithm_used": "fingerprint",
                })

    elif algorithm == "ngram":
        from backend.clustering.algorithms import ngram_similarity as _ng

        processed = set()
        for val in values:
            if val in processed:
                continue
            group_members = [val]
            processed.add(val)
            for other in values:
                if other in processed:
                    continue
                if _ng(val, other) >= threshold:
                    group_members.append(other)
                    processed.add(other)
            if len(group_members) > 1:
                groups.append({
                    "main": val,
                    "variations": group_members,
                    "count": len(group_members),
                    "algorithm_used": "ngram",
                })

    elif algorithm == "phonetic":
        from backend.clustering.algorithms import cologne_phonetic as _col, metaphone as _met

        buckets: dict = {}
        for val in values:
            code = _col(val) or _met(val)
            if code:
                buckets.setdefault(code, []).append(val)
        for members in buckets.values():
            if len(members) > 1:
                main = max(members, key=len)
                groups.append({
                    "main": main,
                    "variations": members,
                    "count": len(members),
                    "algorithm_used": "phonetic",
                })

    if with_total:
        total = len(groups)
        start = skip or 0
        page = groups[start : start + limit] if limit is not None else groups[start:]
        return page, total

    return groups


def _dispatch_webhook(action: str, payload: dict, db_factory) -> None:
    """Fire-and-forget: send POST to every active webhook subscribed to *action*."""

    def _worker():
        import time as _time

        with db_factory() as db:
            hooks = db.query(models.Webhook).filter(
                models.Webhook.is_active == True  # noqa: E712
            ).all()
            body = json.dumps({"event": action, "data": payload}).encode()
            for hook in hooks:
                try:
                    events = json.loads(hook.events or "[]")
                except Exception:
                    events = []
                if action not in events:
                    continue
                headers = {"Content-Type": "application/json", "X-UKIP-Event": action}
                if hook.secret:
                    sig = hmac.new(hook.secret.encode(), body, hashlib.sha256).hexdigest()
                    headers["X-UKIP-Signature"] = f"sha256={sig}"
                req = _urllib_req.Request(hook.url, data=body, headers=headers, method="POST")
                status = 0
                resp_body = None
                error_msg = None
                t0 = _time.monotonic()
                try:
                    with _urllib_req.urlopen(req, timeout=10) as resp:
                        status = resp.status
                        resp_body = resp.read(500).decode("utf-8", errors="replace")
                except Exception as exc:
                    error_msg = str(exc)[:500]
                    logger.warning("Webhook %s delivery failed: %s", hook.url, exc)
                latency_ms = int((_time.monotonic() - t0) * 1000)
                hook.last_triggered_at = datetime.now(timezone.utc)
                hook.last_status = status
                delivery = models.WebhookDelivery(
                    webhook_id=hook.id,
                    event=action,
                    url=hook.url,
                    status_code=status,
                    response_body=resp_body,
                    latency_ms=latency_ms,
                    error=error_msg,
                    success=200 <= status < 300,
                )
                db.add(delivery)
            db.commit()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def _dispatch_webhook_sync(action: str, payload: dict, hook: models.Webhook, db: Session) -> dict:
    """Synchronous single-webhook delivery."""
    import time as _time

    body = json.dumps({"event": action, "data": payload}).encode()
    headers = {"Content-Type": "application/json", "X-UKIP-Event": action}
    if hook.secret:
        sig = hmac.new(hook.secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-UKIP-Signature"] = f"sha256={sig}"
    req = _urllib_req.Request(hook.url, data=body, headers=headers, method="POST")
    status = 0
    resp_body = None
    error_msg = None
    t0 = _time.monotonic()
    try:
        with _urllib_req.urlopen(req, timeout=10) as resp:
            status = resp.status
            resp_body = resp.read(500).decode("utf-8", errors="replace")
    except Exception as exc:
        error_msg = str(exc)[:500]
    latency_ms = int((_time.monotonic() - t0) * 1000)
    hook.last_triggered_at = datetime.now(timezone.utc)
    hook.last_status = status
    delivery = models.WebhookDelivery(
        webhook_id=hook.id,
        event=action,
        url=hook.url,
        status_code=status,
        response_body=resp_body,
        latency_ms=latency_ms,
        error=error_msg,
        success=200 <= status < 300,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return {
        "delivery_id": delivery.id,
        "status_code": status,
        "latency_ms": latency_ms,
        "success": delivery.success,
        "error": error_msg,
        "response_preview": resp_body,
    }


def _get_store_adapter(store: models.StoreConnection):
    """Build adapter from store connection model, decrypting credentials."""
    config = {
        "platform": store.platform,
        "base_url": store.base_url,
        "api_key": decrypt(store.api_key),
        "api_secret": decrypt(store.api_secret),
        "access_token": decrypt(store.access_token),
        "custom_headers": store.custom_headers,
    }
    return get_adapter(store.platform, config)


def _get_active_integration(db: Session):
    """Return the active AI integration with its api_key decrypted for use."""
    integration = (
        db.query(models.AIIntegration)
        .filter(models.AIIntegration.is_active == True)  # noqa: E712
        .first()
    )
    if not integration:
        return None
    db.expunge(integration)
    if integration.api_key:
        integration.api_key = decrypt(integration.api_key)
    return integration


def _serialize_authority_record(r: models.AuthorityRecord) -> dict:
    """Convert ORM record to dict, deserializing all JSON fields."""
    created_at = r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else r.created_at
    confirmed_at = r.confirmed_at.isoformat() if hasattr(r.confirmed_at, "isoformat") else r.confirmed_at
    return {
        "id":               r.id,
        "field_name":       r.field_name,
        "original_value":   r.original_value,
        "authority_source": r.authority_source,
        "authority_id":     r.authority_id,
        "canonical_label":  r.canonical_label,
        "aliases":          json.loads(r.aliases or "[]"),
        "description":      r.description,
        "confidence":       r.confidence,
        "uri":              r.uri,
        "status":           r.status,
        "created_at":       created_at,
        "confirmed_at":     confirmed_at,
        "resolution_status": r.resolution_status or "unresolved",
        "score_breakdown":   json.loads(r.score_breakdown or "{}"),
        "evidence":          json.loads(r.evidence or "[]"),
        "merged_sources":    json.loads(r.merged_sources or "[]"),
        "resolution_route":  r.resolution_route,
        "complexity_score":  r.complexity_score,
        "review_required":   bool(r.review_required),
        "nil_reason":        r.nil_reason,
        "nil_score":         r.nil_score,
        "hierarchy_distance": r.hierarchy_distance,
        "reformulation_applied": bool(r.reformulation_applied),
        "reformulation_gain": r.reformulation_gain,
        "reformulation_cost_estimate": r.reformulation_cost_estimate,
        "reformulation_trace": json.loads(r.reformulation_trace) if r.reformulation_trace else None,
    }


def _serialize_authority_record_link(link: models.AuthorityRecordLink) -> dict:
    """Convert an AuthorityRecordLink ORM row to a response dict."""
    created_at = link.created_at.isoformat() if hasattr(link.created_at, "isoformat") else link.created_at
    confirmed_at = link.confirmed_at.isoformat() if hasattr(link.confirmed_at, "isoformat") else link.confirmed_at
    return {
        "id": link.id,
        "source_authority_record_id": link.source_authority_record_id,
        "target_authority_record_id": link.target_authority_record_id,
        "link_type": link.link_type,
        "confidence": link.confidence,
        "status": link.status,
        "evidence": json.loads(link.evidence or "[]"),
        "created_at": created_at,
        "confirmed_at": confirmed_at,
    }
