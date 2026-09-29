"""The hops allowed to set X-Forwarded-For for the backend (#413).

Behind Traefik and the Next.js rewrite, the backend's TCP peer is always a
proxy, so ``request.client.host`` named a proxy for every request:
the audit log's ``ip_address``, the request log's ``client_ip`` and every rate
limit were keyed on one or two private addresses. uvicorn can take the client
from ``X-Forwarded-For`` instead, trusting it only from the networks listed in
``docker/trusted-proxies.txt``; this module reads that list, for the entrypoint
and for the tests, so both use the same one.

``python -m backend.proxy_networks`` prints it as uvicorn's
``--forwarded-allow-ips`` value. (Not named ``trusted_*``: CodeQL's
sensitive-data heuristic reads that word as a secret, and this is a list of
public address ranges.)
"""
from __future__ import annotations

import ipaddress
from pathlib import Path

PROXY_NETWORKS_FILE = Path(__file__).resolve().parents[1] / "docker" / "trusted-proxies.txt"


def proxy_networks(path: Path = PROXY_NETWORKS_FILE) -> list[str]:
    """Every network in the file, validated; a malformed line raises.

    Validation is the point: a typo, or a ``*`` that would trust any sender,
    fails here (and in CI) instead of silently widening who may name the client.
    """
    networks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            networks.append(str(ipaddress.ip_network(entry)))
    if not networks:
        raise ValueError(f"{path} lists no networks")
    return networks


if __name__ == "__main__":
    print(",".join(proxy_networks()))
