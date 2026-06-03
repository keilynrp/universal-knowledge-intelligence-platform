"""Health endpoint exposes cache backend status (fail-open)."""
import fakeredis

from backend.cache import client as cache_client


def test_cache_status_in_process_when_unconfigured(monkeypatch):
    monkeypatch.setattr(cache_client.config, "REDIS_URL", "", raising=False)
    status = cache_client.cache_status()
    assert status == {"backend": "in-process", "configured": False, "reachable": True}


def test_cache_status_redis_reachable(monkeypatch):
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(cache_client.config, "REDIS_URL", "redis://x:6379/0", raising=False)
    monkeypatch.setattr(cache_client, "get_redis", lambda: fake)
    status = cache_client.cache_status()
    assert status["backend"] == "redis"
    assert status["configured"] is True
    assert status["reachable"] is True


def test_cache_status_redis_unreachable_is_fail_open(monkeypatch):
    monkeypatch.setattr(cache_client.config, "REDIS_URL", "redis://x:6379/0", raising=False)

    def _boom():
        raise RuntimeError("down")

    monkeypatch.setattr(cache_client, "get_redis", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    status = cache_client.cache_status()
    assert status["backend"] == "redis"
    assert status["configured"] is True
    assert status["reachable"] is False  # ping failed, but no exception raised


def test_health_endpoint_includes_cache(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "cache" in body
    assert body["cache"]["backend"] in {"redis", "in-process"}
    # Default test suite has no REDIS_URL → in-process, reachable.
    assert body["cache"]["backend"] == "in-process"
    assert body["cache"]["reachable"] is True
