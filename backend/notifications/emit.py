"""
Unified notification emitter (change: wire-notification-events, Phase 0).

A single :func:`emit_event` fans a domain event out to all four notification
sinks with one call:

    1. Audit log      → in-app Notification Center / bell   (caller's txn)
    2. Webhooks       → customer-registered outbound hooks  (fire-and-forget)
    3. Alert channels → Slack / Teams / Discord / webhook   (fire-and-forget)
    4. Email (SMTP)   → gated by NotificationSettings toggles (fire-and-forget)

Two taxonomies coexist. Audit/webhooks use dotted **action** strings
(``harmonization.apply``, ``upload``, ``authority.confirm``). Alert channels use
the ``ALL_EVENTS`` **event ids** (``harmonization.applied``,
``entities.imported``). :func:`resolve_alert_event` bridges them: a known action
maps to its event id, and an id already in the catalogue passes through — so an
event that has no natural audit action (``report.sent``, ``enrichment.completed``)
can be emitted by passing the id itself as ``action``.

Delivery is inline fire-and-forget (daemon thread + fresh session via
``db_factory``), matching ``backend.routers.deps._dispatch_webhook``. Each async
sink swallows and logs its own exceptions — :func:`emit_event` never raises.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from backend import models
from backend.notifications.alert_sender import ALL_EVENTS, ALL_EVENT_IDS, dispatch_event
from backend.notifications.email_sender import send_notification

logger = logging.getLogger(__name__)

# ── Taxonomy bridges ────────────────────────────────────────────────────────

# Audit/webhook action → alert-channel event id.
_ACTION_TO_ALERT_EVENT: dict[str, str] = {
    "upload":              "entities.imported",
    "pull":                "entities.imported",
    "scheduled_pull":      "import.scheduled",
    "harmonization.apply": "harmonization.applied",
}

# Action/event → the NotificationSettings toggle that gates its email.
_ACTION_TO_EMAIL_TOGGLE: dict[str, str] = {
    "authority.confirm":    "notify_on_authority_confirm",
    "enrichment.completed": "notify_on_enrichment_batch",
}

_EVENT_LABELS: dict[str, str] = {event_id: label for event_id, label, _ in ALL_EVENTS}


def resolve_alert_event(action: str) -> str | None:
    """Return the alert-channel event id for *action*, or None if not alertable."""
    if action in _ACTION_TO_ALERT_EVENT:
        return _ACTION_TO_ALERT_EVENT[action]
    if action in ALL_EVENT_IDS:
        return action
    return None


def email_toggle_for(action: str) -> str | None:
    """Return the NotificationSettings toggle attr gating email for *action*."""
    return _ACTION_TO_EMAIL_TOGGLE.get(action)


def alert_message_for(action: str, payload: dict[str, Any]) -> str:
    """Human-readable headline for the alert-channel message."""
    event = resolve_alert_event(action) or action
    return _EVENT_LABELS.get(event, event.replace(".", " ").replace("_", " ").title())


def build_email_message(action: str, payload: dict[str, Any]) -> tuple[str, str]:
    """Derive (subject, body) for an email notification from action + payload."""
    headline = alert_message_for(action, payload)
    subject = f"UKIP: {headline}"
    lines = [headline, ""]
    for key, value in (payload or {}).items():
        lines.append(f"- {key}: {value}")
    return subject, "\n".join(lines)


# ── Async plumbing ──────────────────────────────────────────────────────────

def _spawn(target: Callable[[], None]) -> None:
    """Run *target* fire-and-forget. Monkeypatched to run inline in tests."""
    threading.Thread(target=target, daemon=True).start()


def _run_alert_dispatch(db_factory, action: str, payload: dict[str, Any], message: str) -> None:
    event = resolve_alert_event(action)
    if not event:
        return
    try:
        with db_factory() as db:
            dispatch_event(db, event, message, payload)
    except Exception:
        logger.warning("alert-channel dispatch failed for action=%s", action, exc_info=True)


def _run_email_dispatch(db_factory, action: str, payload: dict[str, Any]) -> None:
    toggle = email_toggle_for(action)
    if not toggle:
        return
    try:
        with db_factory() as db:
            settings = db.get(models.NotificationSettings, 1)
            if not settings or not settings.enabled or not getattr(settings, toggle, False):
                return
            subject, body = build_email_message(action, payload)
            send_notification(settings, subject, body)
    except Exception:
        logger.warning("email dispatch failed for action=%s", action, exc_info=True)


# ── Public entry point ──────────────────────────────────────────────────────

def emit_outbound(
    action: str,
    payload: dict[str, Any],
    db_factory,
    *,
    alert_message: str | None = None,
) -> None:
    """
    Fire the three fire-and-forget **outbound** sinks (webhook, alert channels,
    email) — but NOT the in-transaction audit write.

    Call this at a site that already writes its own audit row, in place of the
    existing ``_dispatch_webhook(...)`` call (typically just after ``db.commit()``
    so notifications only fire once the event has durably persisted). All three
    sinks read only config rows + the ``payload`` dict, so they never depend on
    the caller's transaction.
    """
    payload = payload or {}

    # Webhooks (existing fire-and-forget).
    from backend.routers.deps import _dispatch_webhook
    _dispatch_webhook(action, payload, db_factory)

    # Alert channels.
    message = alert_message or alert_message_for(action, payload)
    _spawn(lambda: _run_alert_dispatch(db_factory, action, payload, message))

    # Email (gated by settings toggles).
    _spawn(lambda: _run_email_dispatch(db_factory, action, payload))


def emit_event(
    db,
    action: str,
    payload: dict[str, Any],
    db_factory,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    user_id: int | None = None,
    alert_message: str | None = None,
) -> None:
    """
    Fan an event out to every notification sink (audit + the three outbound
    sinks). Use at sites that do NOT already write their own audit row.

    ``db`` is the caller's request session — the audit row is written in that
    transaction and the caller is still responsible for committing. The outbound
    sinks each run fire-and-forget on their own session from ``db_factory``
    (e.g. ``backend.database.SessionLocal``).
    """
    payload = payload or {}

    # Audit → bell/center (in the caller's transaction).
    from backend.routers.deps import _audit
    _audit(db, action, entity_type=entity_type, entity_id=entity_id,
           user_id=user_id, details=payload)

    emit_outbound(action, payload, db_factory, alert_message=alert_message)
