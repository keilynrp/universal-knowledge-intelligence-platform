"""Regression tests for the webhook dispatch thread / StaticPool flake.

A fire-and-forget ``_dispatch_webhook`` thread surviving into a later test
shares the StaticPool in-memory SQLite connection with the test thread; its
commit/rollback can silently discard the test's in-flight transaction
(observed as ``Could not refresh instance '<WorkflowRun ...>'`` in
test_sprint92).
"""
import threading

from backend import models
from backend.routers import deps as deps_module
from backend.routers.deps import _dispatch_webhook, _has_subscribers


class TestDispatchWebhookThreadHygiene:
    def test_no_thread_spawned_without_subscribers(self, db_session, session_factory, monkeypatch):
        """No webhooks subscribed to the event => no DB-touching thread at all."""
        spawned = []
        real_thread = threading.Thread

        def tracking_thread(*args, **kwargs):
            t = real_thread(*args, **kwargs)
            spawned.append(t)
            return t

        monkeypatch.setattr(deps_module.threading, "Thread", tracking_thread)
        _dispatch_webhook("entity.create", {"entity_id": 1}, session_factory)
        assert spawned == []

    def test_thread_spawned_and_registered_with_subscriber(self, db_session, session_factory):
        db_session.add(models.Webhook(
            url="http://127.0.0.1:9/never",  # port 9 (discard): fails fast
            events='["entity.create"]',
            is_active=True,
        ))
        db_session.commit()

        before = list(deps_module._webhook_dispatch_threads)
        _dispatch_webhook("entity.create", {"entity_id": 1}, session_factory)
        new = [t for t in deps_module._webhook_dispatch_threads if t not in before]
        assert len(new) == 1
        new[0].join(timeout=30)
        assert not new[0].is_alive()

    def test_has_subscribers_filters_by_event(self, db_session, session_factory):
        db_session.add(models.Webhook(
            url="http://127.0.0.1:9/never",
            events='["entity.delete"]',
            is_active=True,
        ))
        db_session.commit()
        assert _has_subscribers("entity.delete", session_factory) is True
        assert _has_subscribers("entity.create", session_factory) is False

    def test_inactive_webhook_is_not_a_subscriber(self, db_session, session_factory):
        db_session.add(models.Webhook(
            url="http://127.0.0.1:9/never",
            events='["entity.create"]',
            is_active=False,
        ))
        db_session.commit()
        assert _has_subscribers("entity.create", session_factory) is False
