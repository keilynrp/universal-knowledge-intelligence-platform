"""Contract tests for scientometric enrichment adapters.

Guards an invariant that broke silently in production:

  ``backend.enrichment_worker`` skips any adapter where
  ``getattr(adapter, 'is_active', False)`` is falsy. When an adapter forgets
  to declare ``is_active``, the cascade treats it as inactive without any
  log line, and a whole provider drops out of enrichment unnoticed.

OpenAlex shipped without ``is_active`` for ~3 months; every entity routed
through the cascade fell to Crossref (no affiliations) instead of OpenAlex
(rich affiliations). This test ensures every adapter declares the attribute
explicitly so new adapters can't reintroduce the failure mode.
"""

from __future__ import annotations

import inspect
import pkgutil
from importlib import import_module
from typing import Iterable

import pytest

import backend.adapters.enrichment as enrichment_pkg
from backend.adapters.enrichment.base import BaseScientometricAdapter


def _discover_concrete_adapters() -> Iterable[type]:
    """Walk ``backend.adapters.enrichment`` and yield every concrete subclass
    of ``BaseScientometricAdapter``. Abstract base classes are excluded."""
    found: list[type] = []
    for _finder, name, _ispkg in pkgutil.iter_modules(enrichment_pkg.__path__):
        if name.startswith("_") or name == "base":
            continue
        module = import_module(f"{enrichment_pkg.__name__}.{name}")
        for _attr_name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseScientometricAdapter)
                and obj is not BaseScientometricAdapter
                and not inspect.isabstract(obj)
                and obj.__module__ == module.__name__
            ):
                found.append(obj)
    return found


_ADAPTERS = list(_discover_concrete_adapters())


@pytest.mark.parametrize("adapter_cls", _ADAPTERS, ids=lambda c: c.__name__)
class TestAdapterIsActiveContract:
    """Every concrete adapter must declare ``is_active`` so the cascade can
    inspect activation explicitly. Defaulting to False via ``getattr`` is
    treated as a contract violation."""

    def test_declares_is_active(self, adapter_cls: type) -> None:
        # The class itself must own the attribute (inherited or not), but the
        # critical guarantee is that *something* attached to the class — never
        # missing entirely.
        assert hasattr(adapter_cls, "is_active"), (
            f"{adapter_cls.__name__} does not declare 'is_active'. The "
            f"enrichment cascade falls back to False for missing attributes, "
            f"which silently disables this provider in production."
        )

    def test_is_active_returns_bool(self, adapter_cls: type) -> None:
        # Try to instantiate with no args; adapters that require credentials
        # may raise. In that case we still expect ``is_active`` to be reachable
        # via the class (typically as a property that returns False when no
        # key is configured).
        try:
            instance = adapter_cls()
        except TypeError:
            # Adapter needs credentials; check class-level descriptor instead.
            descriptor = inspect.getattr_static(adapter_cls, "is_active")
            assert isinstance(descriptor, property), (
                f"{adapter_cls.__name__}.is_active should be a property when "
                f"the adapter requires constructor arguments."
            )
            return
        value = instance.is_active
        assert isinstance(value, bool), (
            f"{adapter_cls.__name__}.is_active returned {value!r} ({type(value).__name__}); "
            f"must be a bool so the cascade can branch on it deterministically."
        )


class TestOpenAlexIsActive:
    """Regression: OpenAlex specifically was missing this and dropped out of
    the cascade in production. Pin its expected value so a future refactor
    that gates OpenAlex behind a credential check doesn't silently break it
    (OpenAlex uses a polite-pool mailto and has no required API key)."""

    def test_openalex_is_always_active(self) -> None:
        from backend.adapters.enrichment.openalex import OpenAlexAdapter

        assert OpenAlexAdapter().is_active is True
