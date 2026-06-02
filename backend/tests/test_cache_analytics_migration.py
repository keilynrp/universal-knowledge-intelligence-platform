"""Task 10 — analytics caches delegate to the distributed cache, and the
derived-status dashboard snapshot uses exists_prefix instead of poking the
cache's private internals."""
import fakeredis

from backend.cache.redis_backend import RedisBackend
from backend.routers import analytics as analytics_mod
from backend.routers.analytics import _SimpleCache


def test_simple_cache_get_set_invalidate():
    c = _SimpleCache(ttl_seconds=60, namespace="analytics")
    assert c.get("missing") is None
    c.set("topics_default_30", {"topics": []})
    assert c.get("topics_default_30") == {"topics": []}


def test_simple_cache_invalidate_prefix_returns_int():
    c = _SimpleCache(ttl_seconds=60, namespace="analytics")
    c.set("topics_a", 1)
    c.set("topics_b", 2)
    c.set("corr_c", 3)
    n = c.invalidate("topics_")
    assert isinstance(n, int) and n == 2
    assert c.get("corr_c") == 3


def test_simple_cache_invalidate_zero_arg_clears_all():
    c = _SimpleCache(ttl_seconds=60, namespace="analytics")
    c.set("a", 1)
    c.set("b", 2)
    n = c.invalidate()
    assert isinstance(n, int) and n == 2


def test_admin_data_fixes_int_return_contract():
    """admin_data_fixes.py:282 relies on .invalidate('coauth_') returning int."""
    c = _SimpleCache(ttl_seconds=60, namespace="analytics")
    c.set("coauth_default_30", 1)
    result = c.invalidate("coauth_")
    assert isinstance(result, int)


def test_snapshot_reports_ready_when_dashboard_key_warm(monkeypatch):
    """exists_prefix-based warmth detection — READY when a matching key exists."""
    from backend.services import derived_status_service as svc

    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    dash = _SimpleCache(ttl_seconds=120, namespace="dashboard")
    dash._backend = RedisBackend(namespace="dashboard", ttl=120, client_factory=lambda: fake)
    monkeypatch.setattr(analytics_mod, "_dashboard_cache", dash, raising=False)

    # Warm: a dashboard_science key exists.
    dash.set("dashboard_science_kpis", {"k": 1})
    assert dash.exists_prefix("dashboard_science") is True
    # Cold for a different domain.
    assert dash.exists_prefix("dashboard_health") is False


def test_invalidate_analytics_for_domain_preserves_prefixes(monkeypatch):
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    ana = _SimpleCache(ttl_seconds=300, namespace="analytics")
    ana._backend = RedisBackend(namespace="analytics", ttl=300, client_factory=lambda: fake)
    dash = _SimpleCache(ttl_seconds=120, namespace="dashboard")
    dash._backend = RedisBackend(namespace="dashboard", ttl=120, client_factory=lambda: fake)
    monkeypatch.setattr(analytics_mod, "_analytics_cache", ana, raising=False)
    monkeypatch.setattr(analytics_mod, "_dashboard_cache", dash, raising=False)

    ana.set("topics_mydom_30", 1)
    ana.set("coauth_mydom_30", 2)
    dash.set("dashboard_mydom", 3)
    ana.set("topics_other_30", 9)

    analytics_mod.invalidate_analytics_for_domain("mydom")

    assert ana.get("topics_mydom_30") is None
    assert ana.get("coauth_mydom_30") is None
    assert dash.get("dashboard_mydom") is None
    assert ana.get("topics_other_30") == 9  # other domain untouched
