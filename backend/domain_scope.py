"""
Domain scope contract for UKIP.

Defines the canonical DomainScope type, validator, parser, and SQLAlchemy
filter resolver. All scope-aware backend code uses this module exclusively —
no inline ``== "all"`` / ``== "default"`` comparisons in router files.

Legal DomainScope values
------------------------
- ``"all"``             – aggregate over all records regardless of domain
- ``"domain:{id}"``     – records where domain == id  (exact match, case-sensitive)
- ``"legacy_default"``  – records where domain == "default" OR domain IS NULL
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.sql.elements import BinaryExpression

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

DomainScope = str
"""
A plain ``str`` alias that carries semantic meaning.  Use ``is_valid_scope``
to validate and ``parse_scope`` to convert raw legacy strings.
"""

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_SCOPE_ALL = "all"
_SCOPE_LEGACY = "legacy_default"
_DOMAIN_PREFIX = "domain:"
_DOMAIN_PATTERN = re.compile(r"^domain:.+$")

# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def is_valid_scope(s: object) -> bool:
    """Return ``True`` if *s* is a legal ``DomainScope`` value.

    Valid values:
    - ``"all"``
    - ``"legacy_default"``
    - Any string matching ``^domain:.+$``  (e.g. ``"domain:science"``)

    Examples::

        >>> is_valid_scope("all")
        True
        >>> is_valid_scope("domain:science")
        True
        >>> is_valid_scope("legacy_default")
        True
        >>> is_valid_scope("default")
        False
        >>> is_valid_scope("")
        False
        >>> is_valid_scope("science")
        False
    """
    if not isinstance(s, str):
        return False
    return s in (_SCOPE_ALL, _SCOPE_LEGACY) or bool(_DOMAIN_PATTERN.match(s))


# ---------------------------------------------------------------------------
# Parser — converts legacy raw strings into canonical DomainScope values
# ---------------------------------------------------------------------------


def parse_scope(raw: Optional[str]) -> DomainScope:
    """Convert a raw domain string (from query params, DB, or legacy code)
    into a canonical ``DomainScope``.

    Mapping rules:

    ========================  =========================
    ``raw``                   ``DomainScope`` returned
    ========================  =========================
    ``None`` or ``""``        ``"all"``
    ``"all"``                 ``"all"``
    ``"default"``             ``"legacy_default"``
    ``"legacy_default"``      ``"legacy_default"``
    ``"domain:science"``      ``"domain:science"``
    ``"science"`` (bare ID)   ``"domain:science"``
    ========================  =========================

    Examples::

        >>> parse_scope(None)
        'all'
        >>> parse_scope("")
        'all'
        >>> parse_scope("default")
        'legacy_default'
        >>> parse_scope("science")
        'domain:science'
        >>> parse_scope("domain:science")
        'domain:science'
        >>> parse_scope("all")
        'all'
    """
    if not raw:
        return _SCOPE_ALL
    if raw == _SCOPE_ALL:
        return _SCOPE_ALL
    if raw == "default":
        return _SCOPE_LEGACY
    if raw == _SCOPE_LEGACY:
        return _SCOPE_LEGACY
    # Already prefixed
    if raw.startswith(_DOMAIN_PREFIX):
        return raw
    # Bare domain ID — add prefix
    return f"{_DOMAIN_PREFIX}{raw}"


# ---------------------------------------------------------------------------
# Resolver — converts a DomainScope into a SQLAlchemy filter or None
# ---------------------------------------------------------------------------


def resolve_domain_filter(
    scope: DomainScope,
    model,
) -> Optional[BinaryExpression]:
    """Return a SQLAlchemy filter expression for *scope*, or ``None`` for "all".

    Args:
        scope:  A canonical ``DomainScope`` value.  Pass the output of
                ``parse_scope()`` when the value comes from user input.
        model:  The SQLAlchemy ORM model class that has a ``.domain`` column.

    Returns:
        - ``None``                  when scope is ``"all"`` (caller adds no
                                    WHERE clause on the domain column)
        - ``model.domain == id``    when scope is ``"domain:{id}"``
        - ``or_(model.domain == "default", model.domain.is_(None))``
                                    when scope is ``"legacy_default"``

    Raises:
        ValueError: if *scope* is not a valid DomainScope string.

    Examples::

        >>> resolve_domain_filter("all", RawEntity) is None
        True
        >>> resolve_domain_filter("domain:science", RawEntity)
        <...domain = 'science'>
        >>> resolve_domain_filter("legacy_default", RawEntity)
        <...domain = 'default' OR domain IS NULL>

    Note:
        This resolver does **not** apply tenant / org scoping.  Multi-tenancy
        filtering remains in ``tenant_access.py``.
    """
    if scope == _SCOPE_ALL:
        return None

    if scope == _SCOPE_LEGACY:
        return or_(model.domain == "default", model.domain.is_(None))

    if scope.startswith(_DOMAIN_PREFIX):
        domain_id = scope[len(_DOMAIN_PREFIX):]
        return model.domain == domain_id

    raise ValueError(
        f"Invalid DomainScope: {scope!r}. "
        f"Use parse_scope() to convert raw values first."
    )
