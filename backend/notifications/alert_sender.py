"""
Sprint 81 — Alert sender for Slack / Teams / Discord / generic webhooks, and
Pushover (#377), the one channel that can wake a person.
Uses stdlib urllib only — no extra dependencies.

Ops alerts carry a ``severity`` in their details (``page``, ``urgent`` or
``info``, see ``backend.ops_monitor.severity``). Pushover maps it to a priority;
every other channel shows it as a ``[PAGE]``/``[URGENT]`` prefix, so Slack
readers see the same classification the phone does.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# ── Event catalogue ────────────────────────────────────────────────────────────
# Used by the frontend to render checkboxes and by the router to validate.

ALL_EVENTS = [
    ("entities.imported",      "Entities imported",       "New entities added from file upload or store pull"),
    ("enrichment.completed",   "Enrichment completed",    "Background enrichment pass finished for a domain"),
    ("harmonization.applied",  "Harmonization applied",   "Harmonization rules applied to the dataset"),
    ("quality.low",            "Low quality alert",       "Domain avg quality score drops below threshold"),
    ("report.sent",            "Report delivered",        "Scheduled report successfully sent by email"),
    ("report.failed",          "Report delivery failed",  "Scheduled report email delivery failed"),
    ("import.scheduled",       "Scheduled import done",   "Scheduled store import completed"),
    ("ops.check_failed",       "Operational check failed","Operational checks detected a degraded or critical runtime state"),
    ("disambiguation.resolved","Disambiguation resolved",  "AI disambiguation resolved entity clusters"),
]

ALL_EVENT_IDS = {e[0] for e in ALL_EVENTS}


PUSHOVER_API = "https://api.pushover.net/1/messages.json"
#: Pushover truncates longer messages; truncating here keeps the end readable.
PUSHOVER_MESSAGE_LIMIT = 1024

#: severity -> (priority, retry seconds, expire seconds). Priority 2 is
#: emergency: it breaks through Do Not Disturb and repeats every `retry`
#: seconds until acknowledged or `expire` passes. "test" is a real emergency
#: that stops by itself after a minute (#377: a paging path is only proven on
#: the phone, not by an HTTP 200).
PUSHOVER_PRIORITIES: dict[str, tuple[int, int | None, int | None]] = {
    "page":   (2, 60, 3600),
    "test":   (2, 30, 60),
    "urgent": (1, None, None),
    "info":   (0, None, None),
}

_SEVERITY_PREFIX = {"page": "[PAGE] ", "urgent": "[URGENT] "}


def _decrypt_url(encrypted_url: str) -> str:
    if not encrypted_url:
        return ""
    try:
        from backend.encryption import decrypt_value
        return decrypt_value(encrypted_url)
    except Exception:  # noqa: BLE001 — rows written before encryption hold the plain value
        return encrypted_url


def pushover_credentials(decrypted: str) -> tuple[str, str] | None:
    """The (token, user) a Pushover channel stores as JSON, or None if malformed."""
    try:
        creds = json.loads(decrypted)
    except ValueError:
        return None
    if not isinstance(creds, dict):
        return None
    token, user = creds.get("token"), creds.get("user")
    if isinstance(token, str) and isinstance(user, str) and token and user:
        return token, user
    return None


def build_pushover_fields(
    token: str, user: str, event: str, message: str, details: dict[str, Any]
) -> dict[str, str]:
    """The form fields of one Pushover message. Pure, so the mapping is testable."""
    severity = str(details.get("severity") or "info")
    priority, retry, expire = PUSHOVER_PRIORITIES.get(severity, PUSHOVER_PRIORITIES["info"])
    lines = [message, *(f"{k}: {v}" for k, v in details.items() if k != "severity")]
    body = "\n".join(lines)
    if len(body) > PUSHOVER_MESSAGE_LIMIT:
        body = body[: PUSHOVER_MESSAGE_LIMIT - 1] + "…"
    fields = {
        "token": token,
        "user": user,
        "title": f"UKIP — {event}",
        "message": body,
        "priority": str(priority),
    }
    if retry is not None and expire is not None:
        fields["retry"] = str(retry)
        fields["expire"] = str(expire)
    return fields


def _send_pushover(decrypted: str, event: str, message: str, details: dict[str, Any]) -> bool:
    creds = pushover_credentials(decrypted)
    if creds is None:
        logger.warning("Pushover channel has malformed credentials — skipping")
        return False
    data = urllib.parse.urlencode(build_pushover_fields(*creds, event, message, details)).encode()
    req = urllib.request.Request(
        PUSHOVER_API,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "UKIP-Alerts/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = 200 <= resp.status < 300
            if not ok:
                logger.warning("Pushover delivery failed: HTTP %s for event '%s'", resp.status, event)
            return ok
    except Exception:  # noqa: BLE001 — an alert must never raise into the caller
        # Never include the request: it carries the token and user key.
        logger.warning("Pushover delivery exception for event '%s'", event)
        return False


def _build_slack_payload(event: str, message: str, details: dict[str, Any]) -> dict:
    fields = [{"type": "mrkdwn", "text": f"*{k}*\n{v}"} for k, v in details.items()]
    return {
        "text": f":bell: *UKIP — {message}*",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":bell: *UKIP — {message}*"}},
            *(
                [{"type": "section", "fields": fields}]
                if fields else []
            ),
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Event: `{event}`"}]},
        ],
    }


def _build_teams_payload(event: str, message: str, details: dict[str, Any]) -> dict:
    """Adaptive Card for Teams incoming webhook (version 1.x)."""
    facts = [{"name": k, "value": str(v)} for k, v in details.items()]
    card: dict = {
        "@type":      "MessageCard",
        "@context":   "https://schema.org/extensions",
        "themeColor": "6366f1",
        "summary":    message,
        "sections": [{
            "activityTitle": f"UKIP — {message}",
            "activitySubtitle": f"Event: {event}",
            "facts": facts,
            "markdown": True,
        }],
    }
    return card


def _build_discord_payload(event: str, message: str, details: dict[str, Any]) -> dict:
    fields = [{"name": k, "value": str(v), "inline": True} for k, v in details.items()]
    return {
        "embeds": [{
            "title":       f"UKIP — {message}",
            "color":       0x6366f1,
            "fields":      fields,
            "footer":      {"text": f"Event: {event}"},
        }],
    }


def _build_generic_payload(event: str, message: str, details: dict[str, Any]) -> dict:
    return {"event": event, "message": message, "details": details}


def fire_alert(
    channel_type: str,
    webhook_url_encrypted: str,
    event: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> bool:
    """
    Send an alert to the specified channel.
    Returns True on success (HTTP 2xx), False otherwise.
    Never raises.
    """
    url = _decrypt_url(webhook_url_encrypted)
    if not url:
        logger.warning("Alert channel has empty URL — skipping")
        return False

    details = details or {}
    if channel_type == "pushover":
        return _send_pushover(url, event, message, details)

    message = _SEVERITY_PREFIX.get(str(details.get("severity")), "") + message

    builders = {
        "slack":   _build_slack_payload,
        "teams":   _build_teams_payload,
        "discord": _build_discord_payload,
    }
    builder = builders.get(channel_type, _build_generic_payload)
    payload = builder(event, message, details)

    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "UKIP-Alerts/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = 200 <= resp.status < 300
            if not ok:
                logger.warning("Alert delivery failed: HTTP %s for event '%s'", resp.status, event)
            return ok
    except Exception:
        logger.warning("Alert delivery exception for event '%s'", event, exc_info=True)
        return False


def dispatch_event(db_session, event: str, message: str, details: dict[str, Any] | None = None) -> None:
    """
    Fire all active alert channels subscribed to `event`.
    Meant to be called from other routers — never raises, updates channel stats.
    """
    from datetime import datetime, timezone

    from backend import models

    channels = db_session.query(models.AlertChannel).filter(
        models.AlertChannel.is_active == True,
    ).all()

    now = datetime.now(timezone.utc)
    for ch in channels:
        try:
            subscribed = json.loads(ch.events or "[]")
        except (TypeError, ValueError):
            subscribed = []

        if event not in subscribed:
            continue

        ok = fire_alert(ch.type, ch.webhook_url, event, message, details)
        ch.last_fired_at = now
        ch.last_fire_status = "ok" if ok else "error"
        ch.total_fired = (ch.total_fired or 0) + 1

    try:
        db_session.commit()
    except Exception:
        logger.warning("Failed to update alert channel stats", exc_info=True)
