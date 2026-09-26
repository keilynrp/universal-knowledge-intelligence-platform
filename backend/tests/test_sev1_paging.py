"""A SEV1 wakes a person; anything less does not; silence is noticed (#377).

In the first tabletop detection took 6h22m, overnight, and came from a third
party: alerts reached Slack, which respects Do Not Disturb and does not repeat.
These tests hold the owner's decisions on #377:

- only ``database`` and ``migrations`` going critical page (Pushover
  emergency priority), once per incident;
- ``backup_freshness`` and ``secrets`` critical are urgent, not a page;
- every monitor cycle pings the dead man's switch, ``/fail`` when the
  evaluation itself raised, and nothing about that can break a cycle;
- a Pushover channel's test is a real, self-expiring emergency page.

Nothing here reaches the network: ``urlopen`` is replaced by a recorder.
"""
from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timedelta, timezone

import pytest

from backend import ops_monitor
from backend.notifications import alert_sender
from backend.ops_monitor import (
    PAGE_CHECKS,
    URGENT_CHECKS,
    Observation,
    send_heartbeat,
    severity,
)

NOW = datetime(2026, 9, 26, 3, 0, tzinfo=timezone.utc)
TOKEN = "a" * 30
USER = "u" * 30


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture()
def sent(monkeypatch):
    """Every request urlopen was asked to make, as (url, form fields or None)."""
    calls: list[tuple[str, dict | None]] = []

    def fake_urlopen(request, timeout=None):
        url = request if isinstance(request, str) else request.full_url
        data = None if isinstance(request, str) else request.data
        calls.append((url, dict(urllib.parse.parse_qsl(data.decode())) if data else None))
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return calls


def _obs(critical=frozenset(), status="critical"):
    return Observation(status, frozenset(critical), NOW, frozenset(critical))


# ── Who gets woken up ─────────────────────────────────────────────────────────

def test_the_owner_decision_is_pinned():
    """Changing these sets changes who is paged at 03:00; it must be a reviewed change."""
    assert PAGE_CHECKS == {"database", "migrations"}
    assert URGENT_CHECKS == {"backup_freshness", "secrets"}


@pytest.mark.parametrize(
    ("critical", "previous", "expected"),
    [
        ({"database"}, None, "page"),
        ({"migrations"}, _obs(), "page"),
        ({"database"}, _obs({"database"}), "info"),                    # reminder mid-outage
        ({"database", "migrations"}, _obs({"database"}), "page"),       # a second paging check fails
        ({"database", "backup_freshness"}, _obs({"database"}), "urgent"),  # already paged; SEV2 joins
        ({"backup_freshness"}, None, "urgent"),
        ({"secrets"}, _obs(), "urgent"),
        ({"scheduled_detection"}, None, "info"),
        (set(), _obs({"database"}), "info"),
    ],
)
def test_severity_policy(critical, previous, expected):
    assert severity(frozenset(critical), previous) == expected


def _report(**statuses):
    checks = [{"id": cid, "status": st, "summary": "", "details": {}} for cid, st in statuses.items()]
    worst = "critical" if "critical" in statuses.values() else ("degraded" if statuses else "ok")
    return {
        "status": worst if any(s != "ok" for s in statuses.values()) else "ok",
        "checked_at": NOW.isoformat(),
        "checks": checks,
        "summary": {"critical": sum(s == "critical" for s in statuses.values()),
                    "warning": sum(s == "warning" for s in statuses.values())},
    }


def test_a_database_outage_pages_once_then_recovers_quietly(monkeypatch):
    monkeypatch.setitem(ops_monitor._memory, "last", None)
    dispatched: list[dict] = []
    beats: list[bool] = []

    def cycle(report, at):
        ops_monitor.run_once(
            object(), now=at, run_checks=lambda db: report,
            dispatch=lambda db, event, message, details: dispatched.append(details),
            ingest_evidence=lambda db, now: None, heartbeat=beats.append,
            remind_after=timedelta(hours=1),
        )

    cycle(_report(database="critical"), NOW)
    cycle(_report(database="critical"), NOW + timedelta(hours=2))      # reminder
    cycle(_report(database="ok"), NOW + timedelta(hours=3))            # recovered

    assert [d["severity"] for d in dispatched] == ["page", "info", "info"]
    assert beats == [True, True, True]


def test_a_failed_evaluation_reports_failure_to_the_dead_mans_switch(monkeypatch):
    monkeypatch.setitem(ops_monitor._memory, "last", None)
    beats: list[bool] = []

    def explode(db):
        raise RuntimeError("database gone")

    class _Db:
        def rollback(self):
            pass

    ops_monitor.run_once(
        _Db(), now=NOW, run_checks=explode, dispatch=lambda *a, **k: None,
        ingest_evidence=lambda db, now: None, heartbeat=beats.append,
    )

    assert beats == [False]


# ── The heartbeat ─────────────────────────────────────────────────────────────

def test_heartbeat_pings_the_url_and_fail_on_failure(sent):
    send_heartbeat(True, url="https://hc-ping.com/abc-123")
    send_heartbeat(False, url="https://hc-ping.com/abc-123/")

    assert [url for url, _ in sent] == ["https://hc-ping.com/abc-123", "https://hc-ping.com/abc-123/fail"]


def test_no_heartbeat_url_means_no_request(sent, monkeypatch):
    monkeypatch.delenv(ops_monitor.HEARTBEAT_URL_ENV, raising=False)

    send_heartbeat(True)

    assert sent == []


def test_an_unreachable_heartbeat_never_raises_nor_logs_the_url(monkeypatch, caplog):
    def down(request, timeout=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", down)

    send_heartbeat(True, url="https://hc-ping.com/secret-capability-uuid")

    assert "heartbeat ping failed" in caplog.text
    assert "secret-capability-uuid" not in caplog.text


# ── Pushover delivery ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("severity_", "priority", "retry", "expire"),
    [("page", "2", "60", "3600"), ("test", "2", "30", "60"), ("urgent", "1", None, None), ("info", "0", None, None)],
)
def test_severity_maps_to_pushover_priority(severity_, priority, retry, expire):
    fields = alert_sender.build_pushover_fields(TOKEN, USER, "ops.check_failed", "msg", {"severity": severity_})

    assert fields["priority"] == priority
    assert fields.get("retry") == retry and fields.get("expire") == expire
    assert "severity" not in fields["message"]


def test_a_long_message_is_truncated_to_pushover_limit():
    fields = alert_sender.build_pushover_fields(TOKEN, USER, "e", "x" * 5000, {})

    assert len(fields["message"]) == alert_sender.PUSHOVER_MESSAGE_LIMIT


def test_fire_alert_posts_a_form_to_pushover(sent):
    encrypted = json.dumps({"token": TOKEN, "user": USER})  # _decrypt_url passes plain values through

    ok = alert_sender.fire_alert("pushover", encrypted, "ops.check_failed", "Database down", {"severity": "page"})

    assert ok
    [(url, form)] = sent
    assert url == alert_sender.PUSHOVER_API
    assert form["token"] == TOKEN and form["user"] == USER and form["priority"] == "2"


def test_malformed_pushover_credentials_are_skipped(sent):
    assert alert_sender.fire_alert("pushover", "not json", "e", "m", {}) is False
    assert sent == []


def test_slack_payload_carries_the_page_prefix(monkeypatch):
    captured: list[bytes] = []

    def fake(request, timeout=None):
        captured.append(request.data)
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake)

    alert_sender.fire_alert("slack", "https://hooks.slack.invalid/x", "ops.check_failed", "Database down", {"severity": "page"})

    assert json.loads(captured[0])["text"].startswith(":bell: *UKIP — [PAGE] Database down")


# ── The channel API ───────────────────────────────────────────────────────────

def test_a_pushover_channel_needs_both_keys(client, auth_headers):
    resp = client.post("/alert-channels", json={"name": "Phone", "type": "pushover", "pushover_token": TOKEN}, headers=auth_headers)
    assert resp.status_code == 422

    resp = client.post("/alert-channels", json={"name": "Phone", "type": "pushover", "pushover_token": "short", "pushover_user": USER}, headers=auth_headers)
    assert resp.status_code == 422


def test_url_types_still_need_a_url(client, auth_headers):
    resp = client.post("/alert-channels", json={"name": "Slack", "type": "slack"}, headers=auth_headers)

    assert resp.status_code == 422


def test_pushover_keys_are_stored_but_never_returned(client, auth_headers):
    created = client.post(
        "/alert-channels",
        json={"name": "Phone", "type": "pushover", "pushover_token": TOKEN, "pushover_user": USER, "events": ["ops.check_failed"]},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text

    listed = client.get("/alert-channels", headers=auth_headers).text + client.get(f"/alert-channels/{created.json()['id']}", headers=auth_headers).text
    assert TOKEN not in created.text + listed
    assert USER not in created.text + listed


def test_testing_a_pushover_channel_sends_a_self_expiring_emergency(client, auth_headers, sent):
    created = client.post(
        "/alert-channels",
        json={"name": "Phone", "type": "pushover", "pushover_token": TOKEN, "pushover_user": USER},
        headers=auth_headers,
    ).json()

    resp = client.post(f"/alert-channels/{created['id']}/test", headers=auth_headers)

    assert resp.json()["success"] is True
    [(_, form)] = [c for c in sent if c[0] == alert_sender.PUSHOVER_API]
    assert (form["priority"], form["retry"], form["expire"]) == ("2", "30", "60")
    assert form["token"] == TOKEN and form["user"] == USER


def test_the_heartbeat_url_is_declared_for_production_and_never_committed():
    """A variable the code reads but prod compose does not declare does nothing;
    and the URL is a capability, so the repository carries only an empty default."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker-compose.prod.yml").read_text(encoding="utf-8")
    dokploy = (root / ".env.dokploy.example").read_text(encoding="utf-8")

    assert "UKIP_OPS_HEARTBEAT_URL: ${UKIP_OPS_HEARTBEAT_URL:-}" in compose
    assert "UKIP_OPS_HEARTBEAT_URL=\n" in dokploy
    assert "hc-ping.com" not in compose + dokploy
