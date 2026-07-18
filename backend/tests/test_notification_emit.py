"""
wire-notification-events — Phase 0: unified emitter fan-out.

Covers the emit.py core: action→alert-event mapping, email-toggle gating,
audit write, alert-channel dispatch, and never-raises behavior.

Threads are made deterministic by monkeypatching emit._spawn to run the target
synchronously, so assertions can run immediately after emit_event returns.
"""
from __future__ import annotations

import json

import pytest

from backend import models
from backend.notifications import emit
from backend.notifications.alert_sender import ALL_EVENT_IDS


@pytest.fixture(autouse=True)
def _sync_spawn(monkeypatch):
    """Run fire-and-forget sinks synchronously for deterministic assertions."""
    monkeypatch.setattr(emit, "_spawn", lambda target: target())


# ── Pure mapping / formatter helpers ────────────────────────────────────────

class TestMapping:
    def test_known_actions_map_to_alert_events(self):
        assert emit.resolve_alert_event("upload") == "entities.imported"
        assert emit.resolve_alert_event("pull") == "entities.imported"
        assert emit.resolve_alert_event("harmonization.apply") == "harmonization.applied"
        assert emit.resolve_alert_event("scheduled_pull") == "import.scheduled"

    def test_catalogue_ids_pass_through(self):
        assert emit.resolve_alert_event("report.sent") == "report.sent"
        assert emit.resolve_alert_event("enrichment.completed") == "enrichment.completed"

    def test_unknown_action_maps_to_none(self):
        assert emit.resolve_alert_event("something.random") is None

    def test_every_catalogue_event_is_reachable(self):
        # No advertised event may be silently unwireable.
        for event_id in ALL_EVENT_IDS:
            assert emit.resolve_alert_event(event_id) == event_id

    def test_email_toggle_mapping(self):
        assert emit.email_toggle_for("authority.confirm") == "notify_on_authority_confirm"
        assert emit.email_toggle_for("enrichment.completed") == "notify_on_enrichment_batch"
        assert emit.email_toggle_for("upload") is None


# ── emit_event integration ──────────────────────────────────────────────────

def _active_channel(db, events, ch_type="slack"):
    ch = models.AlertChannel(
        name="Test", type=ch_type, webhook_url="enc://x",
        events=json.dumps(events), is_active=True,
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


class TestEmitEvent:
    def test_writes_audit_row(self, db_session, db_factory):
        emit.emit_event(db_session, "upload", {"filename": "x.csv", "rows": 3}, db_factory,
                        entity_type="entity")
        db_session.commit()
        row = (
            db_session.query(models.AuditLog)
            .filter(models.AuditLog.action == "upload")
            .first()
        )
        assert row is not None
        assert json.loads(row.details)["rows"] == 3

    def test_fires_subscribed_alert_channel(self, db_session, db_factory, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "backend.notifications.alert_sender.fire_alert",
            lambda ch_type, url, event, message, details=None: calls.append(event) or True,
        )
        _active_channel(db_session, ["entities.imported"])

        emit.emit_event(db_session, "upload", {"rows": 1}, db_factory)

        assert calls == ["entities.imported"]

    def test_does_not_fire_unsubscribed_channel(self, db_session, db_factory, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "backend.notifications.alert_sender.fire_alert",
            lambda *a, **k: calls.append(1) or True,
        )
        _active_channel(db_session, ["report.sent"])  # not subscribed to entities.imported

        emit.emit_event(db_session, "upload", {"rows": 1}, db_factory)

        assert calls == []

    def test_email_not_sent_when_toggle_off(self, db_session, db_factory, monkeypatch):
        sent = []
        monkeypatch.setattr(emit, "send_notification",
                            lambda s, subject, body: sent.append(subject) or True)
        db_session.add(models.NotificationSettings(
            id=1, enabled=True, notify_on_authority_confirm=False,
            recipient_email="a@b.com", smtp_host="smtp",
        ))
        db_session.commit()

        emit.emit_event(db_session, "authority.confirm", {"canonical_label": "X"}, db_factory)

        assert sent == []

    def test_email_sent_when_enabled_and_toggle_on(self, db_session, db_factory, monkeypatch):
        sent = []
        monkeypatch.setattr(emit, "send_notification",
                            lambda s, subject, body: sent.append(subject) or True)
        db_session.add(models.NotificationSettings(
            id=1, enabled=True, notify_on_authority_confirm=True,
            recipient_email="a@b.com", smtp_host="smtp",
        ))
        db_session.commit()

        emit.emit_event(db_session, "authority.confirm", {"canonical_label": "X"}, db_factory)

        assert len(sent) == 1

    def test_email_not_sent_when_globally_disabled(self, db_session, db_factory, monkeypatch):
        sent = []
        monkeypatch.setattr(emit, "send_notification",
                            lambda s, subject, body: sent.append(subject) or True)
        db_session.add(models.NotificationSettings(
            id=1, enabled=False, notify_on_authority_confirm=True,
            recipient_email="a@b.com", smtp_host="smtp",
        ))
        db_session.commit()

        emit.emit_event(db_session, "authority.confirm", {"canonical_label": "X"}, db_factory)

        assert sent == []

    def test_outbound_fires_channel_without_writing_audit(self, db_session, db_factory, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "backend.notifications.alert_sender.fire_alert",
            lambda ch_type, url, event, message, details=None: calls.append(event) or True,
        )
        _active_channel(db_session, ["report.sent"])

        emit.emit_outbound("report.sent", {"schedule": "weekly"}, db_factory)
        db_session.commit()

        assert calls == ["report.sent"]
        # emit_outbound must NOT write an audit row (caller owns that).
        assert (
            db_session.query(models.AuditLog)
            .filter(models.AuditLog.action == "report.sent").count() == 0
        )

    def test_never_raises_when_alert_sink_fails(self, db_session, db_factory, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("network down")
        monkeypatch.setattr("backend.notifications.alert_sender.fire_alert", _boom)
        _active_channel(db_session, ["entities.imported"])

        # Should not raise; audit still written.
        emit.emit_event(db_session, "upload", {"rows": 1}, db_factory)
        db_session.commit()
        assert (
            db_session.query(models.AuditLog)
            .filter(models.AuditLog.action == "upload").count() == 1
        )
