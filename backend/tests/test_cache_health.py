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


def test_health_endpoint_reports_build_version(client, monkeypatch):
    """/health.version is the build this container is actually running.

    Dockerfile.backend already bakes the CI commit into UKIP_APP_VERSION, but it
    was never surfaced, so nothing outside the container could tell which build
    was serving. The deploy gate needs exactly this to verify a deploy landed.
    """
    monkeypatch.setenv("UKIP_APP_VERSION", "b72df3ea3669f6f4c3febb970ccc47ea6cf409fd")
    body = client.get("/health").json()
    assert body["version"] == "b72df3ea3669f6f4c3febb970ccc47ea6cf409fd"


def test_health_version_falls_back_when_unset(client, monkeypatch):
    """An unbuilt/local container reports 'local', never an empty string.

    An empty value would make the deploy gate's comparison vacuously pass.
    """
    monkeypatch.delenv("UKIP_APP_VERSION", raising=False)
    body = client.get("/health").json()
    assert body["version"] == "local"


def test_health_endpoint_exposes_feature_flags(client, monkeypatch):
    """/health.features reflects the effective flag state of this container."""
    monkeypatch.setenv("UKIP_AUTO_RESOLVE_ON_INGEST", "1")
    monkeypatch.setenv("UKIP_AUTHORITY_WRITEBACK", "0")
    monkeypatch.setenv("UKIP_USE_BLOCKING", "0")
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    body = client.get("/health").json()
    assert body["features"]["auto_resolve_on_ingest"] is True
    assert body["features"]["authority_writeback"] is False
    assert body["features"]["use_blocking"] is False
    assert body["features"]["retro_events"] is True
