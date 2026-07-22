"""
Operation IDs are the public SDK surface.

Spec: openspec/changes/generate-openapi-clients/specs/generated-api-clients/spec.md
  - "Operation identifiers are a stable public interface"

Generated clients turn each operationId into a method name. FastAPI's default
(`{function}_{path}_{method}`) makes that name a function of *implementation
detail*: renaming a private Python handler silently renames a public SDK
method. These tests pin the decoupling.
"""
from __future__ import annotations

import re

from fastapi import FastAPI

from backend.openapi_ids import operation_id_for


def _ids(app: FastAPI) -> dict[tuple[str, str], str]:
    """{(method, path): operationId} from a freshly generated schema."""
    app.openapi_schema = None  # openapi() memoizes; force regeneration
    spec = app.openapi()
    out: dict[tuple[str, str], str] = {}
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if isinstance(operation, dict) and "operationId" in operation:
                out[(method.upper(), path)] = operation["operationId"]
    return out


# ── Independence from implementation ──────────────────────────────────────────

class TestRenameIndependence:
    def test_same_route_different_function_name_yields_same_id(self) -> None:
        """The property that motivates this whole change."""
        first = FastAPI(generate_unique_id_function=operation_id_for)

        @first.get("/widgets/{widget_id}", tags=["widgets"])
        def read_widget(widget_id: int):  # noqa: ARG001
            return {}

        second = FastAPI(generate_unique_id_function=operation_id_for)

        @second.get("/widgets/{widget_id}", tags=["widgets"])
        def fetch_one_widget_renamed(widget_id: int):  # noqa: ARG001
            return {}

        assert _ids(first) == _ids(second)

    def test_id_does_not_contain_the_function_name(self) -> None:
        app = FastAPI(generate_unique_id_function=operation_id_for)

        @app.post("/widgets", tags=["widgets"])
        def some_internal_handler_name():
            return {}

        assert "some_internal_handler_name" not in "".join(_ids(app).values())

    def test_changing_the_tag_does_not_change_the_id(self) -> None:
        """Tags are documentation grouping; they must not be part of the contract."""
        tagged = FastAPI(generate_unique_id_function=operation_id_for)

        @tagged.get("/entities", tags=["entities"])
        def a():
            return {}

        retagged = FastAPI(generate_unique_id_function=operation_id_for)

        @retagged.get("/entities", tags=["knowledge"])
        def b():
            return {}

        assert _ids(tagged) == _ids(retagged)


# ── Shape ─────────────────────────────────────────────────────────────────────

class TestIdShape:
    def test_derives_from_method_and_path(self) -> None:
        app = FastAPI(generate_unique_id_function=operation_id_for)

        @app.get("/users/me", tags=["users"])
        def h1():
            return {}

        @app.post("/auth/token", tags=["auth"])
        def h2():
            return {}

        ids = _ids(app)
        assert ids[("GET", "/users/me")] == "get_users_me"
        assert ids[("POST", "/auth/token")] == "post_auth_token"

    def test_path_parameters_become_by_clauses(self) -> None:
        app = FastAPI(generate_unique_id_function=operation_id_for)

        @app.delete("/api-keys/{key_id}", tags=["api-keys"])
        def h(key_id: int):  # noqa: ARG001
            return {}

        assert _ids(app)[("DELETE", "/api-keys/{key_id}")] == "delete_api_keys_by_key_id"

    def test_multiple_parameters_stay_positional(self) -> None:
        app = FastAPI(generate_unique_id_function=operation_id_for)

        @app.get("/a/{x}/b/{y}", tags=["t"])
        def h(x: int, y: int):  # noqa: ARG001
            return {}

        assert _ids(app)[("GET", "/a/{x}/b/{y}")] == "get_a_by_x_b_by_y"

    def test_ids_are_safe_identifiers(self) -> None:
        """Generators derive method names from these; punctuation breaks them."""
        from backend.main import app as real_app

        for operation_id in _ids(real_app).values():
            assert re.fullmatch(r"[a-z][a-z0-9_]*", operation_id), operation_id

    def test_method_distinguishes_same_path(self) -> None:
        app = FastAPI(generate_unique_id_function=operation_id_for)

        @app.get("/widgets", tags=["widgets"])
        def g():
            return {}

        @app.post("/widgets", tags=["widgets"])
        def p():
            return {}

        ids = _ids(app)
        assert ids[("GET", "/widgets")] != ids[("POST", "/widgets")]


# ── The real application ──────────────────────────────────────────────────────

class TestRealApplication:
    def test_all_ids_are_unique(self) -> None:
        """A collision would silently drop an endpoint from every client."""
        from backend.main import app as real_app

        ids = list(_ids(real_app).values())
        duplicates = {i for i in ids if ids.count(i) > 1}
        assert duplicates == set()

    def test_generation_is_deterministic(self) -> None:
        from backend.main import app as real_app

        assert _ids(real_app) == _ids(real_app)

    def test_every_id_starts_with_its_method(self) -> None:
        """The invariant of our scheme, and the absence of FastAPI's default.

        Checked as a prefix rather than "no method suffix": a path segment may
        legitimately be a verb (POST /admin/data-lifecycle/delete correctly
        yields post_admin_data_lifecycle_delete), so a suffix heuristic would
        flag correct IDs.
        """
        from backend.main import app as real_app

        wrong = [
            f"{method} {path} -> {operation_id}"
            for (method, path), operation_id in _ids(real_app).items()
            if not operation_id.startswith(f"{method.lower()}_")
            and operation_id != method.lower()
        ]
        assert wrong == []

    def test_representative_ids_are_pinned(self) -> None:
        """Named explicitly so a change to the public surface fails by name."""
        from backend.main import app as real_app

        ids = _ids(real_app)
        assert ids[("POST", "/auth/token")] == "post_auth_token"
        assert ids[("GET", "/entities")] == "get_entities"
        assert ids[("GET", "/users/me")] == "get_users_me"
        assert ids[("POST", "/api-keys")] == "post_api_keys"
        assert ids[("GET", "/embed/{token}/data")] == "get_embed_by_token_data"
        assert ids[("GET", "/health")] == "get_health"
