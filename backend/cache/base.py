"""CacheBackend interface + key/serialization helpers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional


# Sentinel returned by get() to distinguish a real cached None from a miss.
class _Miss:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover
        return "<MISS>"


MISS = _Miss()

# Unlikely-in-data separator + a sentinel for None tuple elements, so
# (None,) and ("",) and ("None",) all produce distinct keys.
_SEP = "|"
_NONE = "\x00"


def make_key(parts) -> str:
    """Deterministically stringify a tuple/str key for Redis."""
    if isinstance(parts, str):
        return parts
    return _SEP.join(_NONE if p is None else str(p) for p in parts)


Serializer = Callable[[Any], Any]      # domain value -> JSON-safe value
Deserializer = Callable[[Any], Any]    # JSON value   -> domain value


class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> Any: ...          # returns value or MISS

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None: ...

    @abstractmethod
    def get_or_load(self, key: str, loader: Callable[[], Any],
                    ttl: Optional[int] = None) -> Any: ...  # caches None too

    @abstractmethod
    def delete(self, key: str) -> bool: ...

    @abstractmethod
    def invalidate_prefix(self, prefix: str = "") -> int: ...  # always int

    @abstractmethod
    def exists_prefix(self, prefix: str) -> bool: ...
