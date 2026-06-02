import fakeredis
from backend.cache import client as cache_client


def test_ping_returns_false_when_unconfigured(monkeypatch):
    monkeypatch.setattr(cache_client, "_pool", None, raising=False)
    monkeypatch.setattr(cache_client.config, "REDIS_URL", "", raising=False)
    assert cache_client.ping() is False


def test_get_redis_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(cache_client, "_pool", None, raising=False)
    monkeypatch.setattr(cache_client.config, "REDIS_URL", "", raising=False)
    assert cache_client.get_redis() is None


def test_ping_true_with_fakeredis(monkeypatch):
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(cache_client, "get_redis", lambda: fake)
    assert cache_client.ping() is True
