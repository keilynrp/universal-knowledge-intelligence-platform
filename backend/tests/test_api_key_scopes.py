"""
Unit tests for API key scope derivation — pure logic, no DB, no FastAPI.

Spec: openspec/changes/enforce-api-key-scopes/specs/api-key-scope-enforcement/spec.md
  - "Required scope is derived from method and route"
  - "Scopes form an escalating hierarchy"
"""
import pytest

from backend.api_key_scopes import (
    ADMIN,
    READ,
    WRITE,
    ADMIN_EXEMPT_PATHS,
    ADMIN_PATHS,
    READ_OVERRIDES,
    satisfies,
    scope_required,
)


# ── Method derivation ─────────────────────────────────────────────────────────

class TestMethodDerivation:
    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    def test_safe_methods_require_read(self, method: str) -> None:
        assert scope_required(method, "/entities") == READ

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_unsafe_methods_require_write(self, method: str) -> None:
        assert scope_required(method, "/entities/{entity_id}") == WRITE

    def test_method_is_case_insensitive(self) -> None:
        assert scope_required("get", "/entities") == READ
        assert scope_required("post", "/entities") == WRITE

    def test_unknown_method_defaults_to_write(self) -> None:
        """Fail-closed: an unrecognized method must not be treated as a read."""
        assert scope_required("TRACE", "/entities") == WRITE
        assert scope_required("", "/entities") == WRITE


# ── Admin paths ───────────────────────────────────────────────────────────────

class TestAdminPaths:
    @pytest.mark.parametrize(
        "path",
        [
            "/users",
            "/users/{user_id}",
            "/api-keys",
            "/api-keys/{key_id}",
            "/organizations/{org_id}/members",
            "/stores/{store_id}/pull",
            "/admin/data-lifecycle/purge",
            "/ops/secrets",
            "/settings/auth",
            "/auth/sso/settings",
            "/webhooks",
            "/alert-channels/{channel_id}",
        ],
    )
    def test_admin_paths_require_admin_on_reads(self, path: str) -> None:
        assert scope_required("GET", path) == ADMIN

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
    def test_admin_wins_over_method(self, method: str) -> None:
        assert scope_required(method, "/users/{user_id}") == ADMIN

    def test_api_keys_are_admin_gated_to_block_escalation(self) -> None:
        """A write key must not be able to mint a broader key."""
        assert scope_required("POST", "/api-keys") == ADMIN

    def test_prefix_match_respects_segment_boundary(self) -> None:
        """'/users' must not swallow an unrelated route that merely starts with it."""
        assert scope_required("GET", "/users-summary") != ADMIN

    def test_admin_paths_are_normalized(self) -> None:
        """Every configured prefix is absolute and carries no trailing slash."""
        for prefix in ADMIN_PATHS:
            assert prefix.startswith("/")
            assert prefix == "/" or not prefix.endswith("/")


class TestAdminExemptions:
    @pytest.mark.parametrize(
        "method,path,expected",
        [
            ("GET", "/users/me", READ),
            ("PATCH", "/users/me/profile", WRITE),
            ("POST", "/users/me/password", WRITE),
            ("DELETE", "/users/me/avatar", WRITE),
        ],
    )
    def test_self_service_routes_are_not_admin(
        self, method: str, path: str, expected: str
    ) -> None:
        """Self-service lives under an admin prefix but is not an admin surface."""
        assert scope_required(method, path) == expected

    def test_exemption_does_not_leak_to_siblings(self) -> None:
        assert scope_required("GET", "/users/{user_id}") == ADMIN

    def test_every_exemption_sits_under_an_admin_path(self) -> None:
        """An exemption for a non-admin path would be dead configuration."""
        for exempt in ADMIN_EXEMPT_PATHS:
            assert any(
                exempt == p or exempt.startswith(p + "/") for p in ADMIN_PATHS
            ), f"{exempt} exempts nothing"


# ── Read overrides ────────────────────────────────────────────────────────────

class TestReadOverrides:
    @pytest.mark.parametrize(
        "path",
        [
            "/rag/query",
            "/nlq/query",
            "/cube/query",
            "/analyze",
            "/upload/preview",
            "/exports/pdf",
            "/scientific/search",
        ],
    )
    def test_query_posts_require_only_read(self, path: str) -> None:
        assert scope_required("POST", path) == READ

    def test_override_does_not_apply_to_other_methods(self) -> None:
        assert scope_required("DELETE", "/rag/query") == WRITE

    def test_unlisted_post_still_requires_write(self) -> None:
        assert scope_required("POST", "/entities/quality/compute") == WRITE

    def test_override_cannot_weaken_an_admin_path(self) -> None:
        """Admin classification is evaluated first and is not overridable."""
        for method, path in READ_OVERRIDES:
            assert scope_required(method, path) == READ, (
                f"{method} {path} is registered as a read override but resolves "
                f"to {scope_required(method, path)} — it likely sits under an "
                f"admin path, making the override dead configuration."
            )


# ── Hierarchy ─────────────────────────────────────────────────────────────────

class TestHierarchy:
    @pytest.mark.parametrize(
        "granted,required,expected",
        [
            (["read"], READ, True),
            (["read"], WRITE, False),
            (["read"], ADMIN, False),
            (["write"], READ, True),
            (["write"], WRITE, True),
            (["write"], ADMIN, False),
            (["admin"], READ, True),
            (["admin"], WRITE, True),
            (["admin"], ADMIN, True),
        ],
    )
    def test_satisfaction_matrix(
        self, granted: list[str], required: str, expected: bool
    ) -> None:
        assert satisfies(granted, required) is expected

    def test_multiple_scopes_union(self) -> None:
        assert satisfies(["read", "write"], WRITE) is True
        assert satisfies(["read", "write"], ADMIN) is False

    def test_empty_scopes_satisfy_nothing(self) -> None:
        assert satisfies([], READ) is False

    def test_unknown_scope_is_ignored(self) -> None:
        """A scope value we do not recognize must not grant anything."""
        assert satisfies(["superuser"], READ) is False
        assert satisfies(["superuser", "read"], READ) is True

    def test_scope_values_are_case_sensitive(self) -> None:
        """The API validates scopes on creation; we do not silently coerce."""
        assert satisfies(["READ"], READ) is False
