"""The backend names the client, not the proxy in front of it (#413).

In production every request reached the backend from a proxy: 15 audit rows in
a week came from 2 addresses, all private. The audit log, the request log and
every rate limit were keyed on those. uvicorn now takes the client from
X-Forwarded-For, trusting it only from ``docker/trusted-proxies.txt``.

These tests run uvicorn's own ProxyHeadersMiddleware, as the entrypoint
configures it, over each path a request takes in production:

    client ─▶ Traefik ─┬─▶ Next.js rewrite ─▶ backend   (browser)
                       └─▶ backend                      (API keys)

Traefik is the edge: DNS points straight at the VPS, with no CDN in front
(checked 2026-09-29). Without ``forwardedHeaders`` it replaces any incoming
X-Forwarded-For with the address that connected, which is the client. Next.js
16 forwards the header as it receives it, and sets it to its peer only when
absent (next/dist/server/base-server.js), so both paths deliver Traefik's
header to the backend.
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

from backend.proxy_networks import PROXY_NETWORKS_FILE, proxy_networks

ROOT = Path(__file__).resolve().parents[2]

CLIENT = "203.0.113.7"          # a real client, documentation range
OTHER_CLIENT = "198.51.100.23"
TRAEFIK = "10.0.1.2"            # Docker overlay network
FRONTEND = "10.0.1.5"
ATTACKER = "192.0.2.66"         # reaches the backend port from outside the host
CDN_ADDRESS = "162.158.1.1"     # a Cloudflare range: public, so never trusted


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
    middleware = ProxyHeadersMiddleware(app, trusted_hosts=proxy_networks())
    asyncio.run(middleware(scope, None, None))
    return seen["host"]


class TestPathsInProduction:
    def test_browser_request_through_the_nextjs_rewrite(self):
        assert _client_seen(FRONTEND, CLIENT) == CLIENT

    def test_api_key_request_straight_from_traefik(self):
        assert _client_seen(TRAEFIK, CLIENT) == CLIENT

    def test_ipv6_client(self):
        assert _client_seen(TRAEFIK, "2001:db8::1") == "2001:db8::1"


class TestForgery:
    def test_a_forged_header_does_not_survive_traefik(self):
        # Traefik trusts no forwarded header from the internet, so what reaches
        # the backend is the attacker's own address, whatever they sent.
        assert _client_seen(TRAEFIK, ATTACKER) == ATTACKER

    def test_a_header_from_an_untrusted_peer_is_ignored(self):
        # Someone reaching the backend port from outside the host.
        assert _client_seen(ATTACKER, CLIENT) == ATTACKER

    def test_no_public_hop_is_skipped(self):
        # If a public address ever sat to the right of the client (a CDN that
        # is not in front of this host), the backend stops there instead of
        # believing what that hop claims.
        assert _client_seen(TRAEFIK, f"{CLIENT}, {CDN_ADDRESS}") == CDN_ADDRESS


class TestRateLimitsArePerClient:
    def test_two_clients_no_longer_share_a_bucket(self):
        first = _client_seen(FRONTEND, CLIENT)
        second = _client_seen(FRONTEND, OTHER_CLIENT)
        assert first != second
        assert FRONTEND not in (first, second)


class TestTheList:
    def test_it_trusts_internal_networks_only(self):
        for network in proxy_networks():
            parsed = ipaddress.ip_network(network)
            assert parsed.is_private or parsed.is_loopback, network

    def test_it_never_trusts_everyone(self):
        assert "*" not in PROXY_NETWORKS_FILE.read_text(encoding="utf-8").split()
        assert "0.0.0.0/0" not in proxy_networks()
        assert "::/0" not in proxy_networks()

    def test_a_malformed_entry_fails_loudly(self, tmp_path):
        bad = tmp_path / "trusted.txt"
        bad.write_text("10.0.0.0/8\n10.0.0.300/32\n", encoding="utf-8")
        with pytest.raises(ValueError):
            proxy_networks(bad)

    def test_the_entrypoint_passes_it_to_uvicorn(self):
        entrypoint = (ROOT / "docker/backend-entrypoint.sh").read_text(encoding="utf-8")
        assert "python -m backend.proxy_networks" in entrypoint
        assert '--forwarded-allow-ips "$FORWARDED_ALLOW_IPS"' in entrypoint


class TestTraefikIsTheEdge:
    def test_no_entry_point_trusts_forwarded_headers(self):
        config = yaml.safe_load(
            (ROOT / "deploy/traefik/entrypoints.yml").read_text(encoding="utf-8")
        )
        for name, entry_point in config["entryPoints"].items():
            forwarded = entry_point.get("forwardedHeaders") or {}
            assert not forwarded.get("trustedIPs"), name
            assert not forwarded.get("insecure"), name
