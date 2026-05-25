"""Feature Flags — Task 5.1.

Simple feature flag system for domain-agnostic core boundary.
Flags read from environment variables with sensible defaults.
"""
from __future__ import annotations

import os
from typing import Any


# Known feature flags with defaults
_FLAG_DEFAULTS: dict[str, bool] = {
    "ENABLE_COMMERCE_ADAPTERS": True,
    "ENABLE_LINKED_DATA_EXPORT": True,
    "ENABLE_STAKEHOLDER_DEMO": True,
}


def is_enabled(flag_name: str) -> bool:
    """Check if a feature flag is enabled.

    Reads from environment variable (case-insensitive truthy: "1", "true", "yes").
    Falls back to default if not set.
    """
    env_val = os.environ.get(flag_name)
    if env_val is not None:
        return env_val.strip().lower() in ("1", "true", "yes")
    return _FLAG_DEFAULTS.get(flag_name, False)


def get_all_flags() -> dict[str, bool]:
    """Return all known flags with their current values."""
    return {name: is_enabled(name) for name in _FLAG_DEFAULTS}


def commerce_adapters_enabled() -> bool:
    """Convenience: check if commerce adapters are active."""
    return is_enabled("ENABLE_COMMERCE_ADAPTERS")


# --- Commerce adapter visibility ---

_COMMERCE_STORE_TYPES = frozenset({"shopify", "woocommerce", "bsale", "custom"})


def visible_store_types() -> set[str]:
    """Return store types visible in nav/UI based on feature flags."""
    if commerce_adapters_enabled():
        return set(_COMMERCE_STORE_TYPES)
    return set()


def is_commerce_store_type(store_type: str) -> bool:
    """Check if a store type is a commerce adapter."""
    return store_type.lower() in _COMMERCE_STORE_TYPES
