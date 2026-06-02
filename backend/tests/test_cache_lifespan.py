"""Task 11 — lifespan cache probe/close are safe with REDIS_URL unset."""
from backend.cache import client as cache_client


def test_ping_safe_when_unconfigured(monkeypatch):
    monkeypatch.setattr(cache_client, "_pool", None, raising=False)
    monkeypatch.setattr(cache_client.config, "REDIS_URL", "", raising=False)
    # Must not raise and must report unreachable (in-process path).
    assert cache_client.ping() is False


def test_close_is_idempotent_and_safe(monkeypatch):
    monkeypatch.setattr(cache_client, "_pool", None, raising=False)
    # close() with no pool is a no-op; calling twice must not raise.
    cache_client.close()
    cache_client.close()
