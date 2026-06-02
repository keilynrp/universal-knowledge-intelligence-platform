"""Runtime configuration for the distributed cache layer."""
import os

# When empty/unset, the cache factory selects the in-process backend
# (today's behavior). Setting this in production is the Redis cutover switch.
REDIS_URL: str = os.environ.get("REDIS_URL", "")

# Namespaces every key so multiple deployments can share one Redis instance.
GLOBAL_PREFIX: str = os.environ.get("UKIP_CACHE_PREFIX", "ukip")

# Keep Redis hiccups from stalling request handlers; fail-open kicks in fast.
SOCKET_CONNECT_TIMEOUT: float = float(os.environ.get("UKIP_CACHE_CONNECT_TIMEOUT", "0.5"))
SOCKET_TIMEOUT: float = float(os.environ.get("UKIP_CACHE_SOCKET_TIMEOUT", "0.5"))
