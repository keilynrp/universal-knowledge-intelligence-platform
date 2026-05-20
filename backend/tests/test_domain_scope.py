"""Unit tests for backend.domain_scope — canonical DomainScope contract."""
import pytest
from sqlalchemy import Column, String
from sqlalchemy.orm import declarative_base

from backend.domain_scope import (
    DomainScope,
    is_valid_scope,
    parse_scope,
    resolve_domain_filter,
)

# ---------------------------------------------------------------------------
# Minimal stub model for filter expression tests
# ---------------------------------------------------------------------------

_Base = declarative_base()


class _FakeEntity(_Base):
    __tablename__ = "fake_entity"
    id = Column(String, primary_key=True)
    domain = Column(String)


# ---------------------------------------------------------------------------
# is_valid_scope
# ---------------------------------------------------------------------------


class TestIsValidScope:
    def test_all_is_valid(self):
        assert is_valid_scope("all") is True

    def test_legacy_default_is_valid(self):
        assert is_valid_scope("legacy_default") is True

    def test_domain_prefix_is_valid(self):
        assert is_valid_scope("domain:science") is True
        assert is_valid_scope("domain:healthcare") is True
        assert is_valid_scope("domain:a") is True  # single-char id is fine

    def test_bare_default_is_invalid(self):
        assert is_valid_scope("default") is False

    def test_empty_string_is_invalid(self):
        assert is_valid_scope("") is False

    def test_bare_domain_id_without_prefix_is_invalid(self):
        assert is_valid_scope("science") is False
        assert is_valid_scope("healthcare") is False

    def test_domain_prefix_without_id_is_invalid(self):
        # "domain:" with no ID after the colon
        assert is_valid_scope("domain:") is False

    def test_none_is_invalid(self):
        assert is_valid_scope(None) is False  # type: ignore[arg-type]

    def test_integer_is_invalid(self):
        assert is_valid_scope(42) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# parse_scope
# ---------------------------------------------------------------------------


class TestParseScope:
    def test_none_becomes_all(self):
        assert parse_scope(None) == "all"

    def test_empty_string_becomes_all(self):
        assert parse_scope("") == "all"

    def test_all_passes_through(self):
        assert parse_scope("all") == "all"

    def test_default_becomes_legacy_default(self):
        assert parse_scope("default") == "legacy_default"

    def test_legacy_default_passes_through(self):
        assert parse_scope("legacy_default") == "legacy_default"

    def test_bare_domain_id_gets_prefixed(self):
        assert parse_scope("science") == "domain:science"
        assert parse_scope("healthcare") == "domain:healthcare"
        assert parse_scope("my-custom-domain") == "domain:my-custom-domain"

    def test_already_prefixed_domain_passes_through(self):
        assert parse_scope("domain:science") == "domain:science"
        assert parse_scope("domain:healthcare") == "domain:healthcare"

    def test_result_is_always_valid_scope(self):
        """Whatever parse_scope returns must pass is_valid_scope."""
        inputs = [None, "", "all", "default", "science", "domain:science", "legacy_default"]
        for raw in inputs:
            result = parse_scope(raw)
            assert is_valid_scope(result), f"parse_scope({raw!r}) = {result!r} is not valid"


# ---------------------------------------------------------------------------
# resolve_domain_filter
# ---------------------------------------------------------------------------


class TestResolveDomainFilter:
    def test_all_scope_returns_none(self):
        result = resolve_domain_filter("all", _FakeEntity)
        assert result is None

    def test_all_scope_means_no_where_clause(self):
        """Calling resolve and getting None should produce no filter."""
        filt = resolve_domain_filter("all", _FakeEntity)
        assert filt is None  # caller adds nothing to the query

    def test_domain_scope_produces_equality_filter(self):
        filt = resolve_domain_filter("domain:science", _FakeEntity)
        assert filt is not None
        # Compile to string to inspect — avoids tying test to internal SA objects
        from sqlalchemy.dialects import sqlite
        sql = str(filt.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        assert "science" in sql
        assert "fake_entity.domain" in sql

    def test_legacy_default_scope_produces_or_filter(self):
        filt = resolve_domain_filter("legacy_default", _FakeEntity)
        assert filt is not None
        from sqlalchemy.dialects import sqlite
        sql = str(filt.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        assert "default" in sql
        assert "NULL" in sql.upper() or "IS NULL" in sql.upper()

    def test_invalid_scope_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid DomainScope"):
            resolve_domain_filter("default", _FakeEntity)  # type: ignore[arg-type]

    def test_bare_domain_id_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid DomainScope"):
            resolve_domain_filter("science", _FakeEntity)  # type: ignore[arg-type]

    def test_resolver_does_not_import_tenant_access(self):
        """The resolver module must not depend on tenant_access."""
        import importlib
        import sys
        # domain_scope should be importable without tenant_access being loaded
        if "backend.domain_scope" in sys.modules:
            mod = sys.modules["backend.domain_scope"]
        else:
            mod = importlib.import_module("backend.domain_scope")
        # tenant_access must NOT be a direct dependency of domain_scope
        src = getattr(mod, "__file__", "")
        if src:
            import re as _re
            with open(src) as f:
                content = f.read()
            # Check that there are no import statements referencing tenant_access
            import_lines = [
                line for line in content.splitlines()
                if _re.match(r"^\s*(import|from)\s+.*tenant_access", line)
            ]
            assert not import_lines, (
                f"domain_scope.py must not import tenant_access; found: {import_lines}"
            )
