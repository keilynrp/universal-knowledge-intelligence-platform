"""The backend names the client, not the proxy in front of it (#413).

In production every request reached the backend from a proxy: 15 audit rows in
a week came from 2 addresses, all private. The audit log, the request log and
every rate limit were keyed on those. uvicorn now takes the client from
X-Forwarded-For, trusting it only from ``docker/trusted-proxies.txt``.

These tests run uvicorn's own ProxyHeadersMiddleware, as the entrypoint
configures it, over each path a request takes in production:

    client ─▶ Cloudflare ─▶ Traefik ─┬─▶ Next.js rewrite ─▶ backend   (browser)
                                     └─▶ backend                      (API keys)

Next.js 16 forwards X-Forwarded-For as it receives it, and sets it to its peer
only when absent (next/dist/server/base-server.js), so both paths deliver
Traefik's header to the backend.
"""
from __future__ import annotations

import asyncio
import ipaddress
from pathlib import Path

import pytest
import yaml
from slowapi.util import get_remote_address
from starlette.requests import Request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from backend.trusted_proxies import TRUSTED_PROXIES_FILE, trusted_proxies

ROOT = Path(__file__).resolve().parents[2]

CLIENT = "203.0.113.7"          # a real client, documentation range
OTHER_CLIENT = "198.51.100.23"
CF_EDGE = "162.158.1.1"         # inside Cloudflare's 162.158.0.0/15
TRAEFIK = "10.0.1.2"            # Docker overlay network
FRONTEND = "10.0.1.5"
ATTACKER = "192.0.2.66"         # connects to the origin directly


def _client_seen(peer: str, forwarded_for: str | None) -> str:
    """What the backend records as the client, after uvicorn's middleware."""
    seen: dict[str, str] = {}

    async def app(scope, receive, send):
        seen["host"] = get_remote_address(Request(scope))

    headers = [(b"x-forwarded-for", forwarded_for.encode())] if forwarded_for else []
    scope = {
        "type": "http", "method": "GET", "path": "/entities", "headers": headers,
        "client": (peer, 40000), "server": ("backend", 8000), "scheme": "http",
        "query_string": b"",
    }
    middleware = ProxyHeadersMiddleware(app, trusted_hosts=trusted_proxies())
    asyncio.run(middleware(scope, None, None))
    return seen["host"]


class TestPathsInProduction:
    def test_browser_request_through_the_nextjs_rewrite(self):
        # Traefik trusts Cloudflare, keeps its header and appends the edge.
        assert _client_seen(FRONTEND, f"{CLIENT}, {CF_EDGE}") == CLIENT

    def test_api_key_request_straight_from_traefik(self):
        assert _client_seen(TRAEFIK, f"{CLIENT}, {CF_EDGE}") == CLIENT

    def test_ipv6_client_through_cloudflare(self):
        assert _client_seen(TRAEFIK, "2001:db8::1, 2606:4700::10") == "2001:db8::1"

    def test_without_cloudflare_in_front_the_peer_traefik_saw_is_the_client(self):
        # DNS-only record: Traefik writes the client itself.
        assert _client_seen(TRAEFIK, CLIENT) == CLIENT

    def test_before_traefik_trusts_cloudflare_it_is_the_edge(self):
        # Until deploy/traefik/forwarded-headers.yml is applied, Traefik
        # replaces Cloudflare's header with the edge address. Recorded here so
        # nobody mistakes that interim state for the fix.
        assert _client_seen(TRAEFIK, CF_EDGE) == CF_EDGE


class TestForgery:
    def test_addresses_forged_to_the_left_are_never_reached(self):
        # Sent through Cloudflare with a forged header: Cloudflare appends the
        # real client, Traefik appends the edge.
        forged = f"6.6.6.6, 10.9.9.9, {CLIENT}, {CF_EDGE}"
        assert _client_seen(TRAEFIK, forged) == CLIENT

    def test_a_header_from_an_untrusted_peer_is_ignored(self):
        # Someone reaching the backend port from outside the host.
        assert _client_seen(ATTACKER, f"{CLIENT}, {CF_EDGE}") == ATTACKER

    def test_traefik_replaces_the_header_of_a_direct_origin_request(self):
        # Traefik does not trust the attacker, so it overwrites the header
        # with the attacker's address before the backend sees it.
        assert _client_seen(TRAEFIK, ATTACKER) == ATTACKER


class TestRateLimitsArePerClient:
    def test_two_clients_no_longer_share_a_bucket(self):
        first = _client_seen(FRONTEND, f"{CLIENT}, {CF_EDGE}")
        second = _client_seen(FRONTEND, f"{OTHER_CLIENT}, {CF_EDGE}")
        assert first != second
        assert FRONTEND not in (first, second)


class TestTheList:
    def test_it_never_trusts_everyone(self):
        assert "*" not in TRUSTED_PROXIES_FILE.read_text(encoding="utf-8").split()
        assert "0.0.0.0/0" not in trusted_proxies()
        assert "::/0" not in trusted_proxies()

    def test_a_malformed_entry_fails_loudly(self, tmp_path):
        bad = tmp_path / "trusted.txt"
        bad.write_text("10.0.0.0/8\n10.0.0.300/32\n", encoding="utf-8")
        with pytest.raises(ValueError):
            trusted_proxies(bad)

    def test_the_entrypoint_passes_it_to_uvicorn(self):
        entrypoint = (ROOT / "docker/backend-entrypoint.sh").read_text(encoding="utf-8")
        assert "python -m backend.trusted_proxies" in entrypoint
        assert '--forwarded-allow-ips "$FORWARDED_ALLOW_IPS"' in entrypoint

    def test_traefik_trusts_exactly_cloudflare(self):
        internal = [ipaddress.ip_network(n) for n in ("127.0.0.0/8", "10.0.0.0/8",
                    "172.16.0.0/12", "192.168.0.0/16", "::1/128", "fc00::/7")]
        cloudflare = {
            n for n in trusted_proxies()
            if not any(ipaddress.ip_network(n).subnet_of(i) for i in internal
                       if ipaddress.ip_network(n).version == i.version)
        }
        config = yaml.safe_load(
            (ROOT / "deploy/traefik/forwarded-headers.yml").read_text(encoding="utf-8")
        )
        for name, entry_point in config["entryPoints"].items():
            trusted = {str(ipaddress.ip_network(n)) for n in entry_point["forwardedHeaders"]["trustedIPs"]}
            assert trusted == cloudflare, name
