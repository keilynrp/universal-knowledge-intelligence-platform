"""Paginated list endpoints must return a window in a defined order.

`LIMIT`/`OFFSET` without an `ORDER BY` does not paginate. It slices whatever
order the database happens to produce, and PostgreSQL documents that order as
undefined: the planner is free to return rows in physical heap order, and that
order changes as rows are updated, deleted and re-inserted. A row can then be
delivered on two pages, or on none. `postgres-smoke` caught this as
`test_avatar_returned_in_list_users` failing — a user that had just been
updated was absent from a listing that had to contain it.

SQLite hides the defect. It returns rows in rowid order, which tracks insertion
order closely enough that an unordered query looks sorted, so these tests pass
on SQLite whether or not the endpoints are fixed. PostgreSQL is where they bite,
which is the point: the bug was invisible until the suite ran on both.

**These tests assert the contract, not the symptom.** Reproducing the symptom is
not deterministic — whether an updated row keeps its place depends on free space
in its heap page, and whether a re-inserted row lands early depends on whether
`VACUUM` has run. Both were tried and both passed against an unfixed endpoint
often enough to be worthless as a gate. What is deterministic is that rows
inserted in one order and requested in another must come back in the requested
one: the setup below writes rows with **descending** ids, so physical order is
the exact reverse of id order, and only an endpoint that orders can return them
ascending.
"""

import uuid

from sqlalchemy import func, text

from backend import models
import pytest

pytestmark = pytest.mark.postgres

def _fresh_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _next_id_block(db, model, count: int) -> list[int]:
    """A private, descending block of ids above everything already stored.

    Derived per call rather than from a module constant: the session-scoped
    database keeps `users` between tests, so a fixed base collides with the
    previous test's rows the moment a second test seeds one.
    """
    highest = db.query(func.max(model.id)).scalar() or 0
    base = max(highest, 900_000) + 1_000
    return list(range(base + count, base, -1))


def _sync_sequence(db, table: str) -> None:
    """Explicit ids do not advance a PostgreSQL sequence — move it past them.

    Without this, the next ordinary insert in the same session reuses an id
    this block already took and fails on the primary key, in an unrelated test.
    """
    if db.bind.dialect.name != "postgresql":
        return
    db.execute(
        text(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
            f"(SELECT MAX(id) FROM {table}))"
        )
    )
    db.commit()


def _seed_users_descending(session_factory, count: int) -> list[int]:
    """Write `count` users whose physical order is the reverse of their ids."""
    with session_factory() as db:
        ids = _next_id_block(db, models.User, count)
        for row_id in ids:
            username = _fresh_name("pagi")
            db.add(
                models.User(
                    id=row_id,
                    username=username,
                    email=f"{username}@example.test",
                    password_hash="x",
                    role="viewer",
                    is_active=True,
                )
            )
            db.flush()
        db.commit()
        _sync_sequence(db, "users")
    return ids


def _seed_scrapers_descending(session_factory, count: int) -> list[int]:
    with session_factory() as db:
        ids = _next_id_block(db, models.WebScraperConfig, count)
        for row_id in ids:
            db.add(
                models.WebScraperConfig(
                    id=row_id,
                    name=_fresh_name("pagi"),
                    url_template="https://example.test/{id}",
                    selector="div.result",
                    is_active=True,
                )
            )
            db.flush()
        db.commit()
        _sync_sequence(db, "web_scraper_configs")
    return ids


def _page_ids(client, headers, path: str, page_size: int) -> list[int]:
    collected: list[int] = []
    skip = 0
    while True:
        r = client.get(f"{path}?skip={skip}&limit={page_size}", headers=headers)
        assert r.status_code == 200, r.text
        batch = r.json()
        if not batch:
            break
        collected.extend(row["id"] for row in batch)
        skip += page_size
    return collected


class TestUserListingOrder:
    def test_listing_is_ordered_by_id(self, client, auth_headers, session_factory):
        seeded = _seed_users_descending(session_factory, 40)

        r = client.get("/users?skip=0&limit=500", headers=auth_headers)
        assert r.status_code == 200, r.text
        returned = [u["id"] for u in r.json() if u["id"] in set(seeded)]

        assert returned == sorted(seeded), (
            "the listing came back in an order the endpoint never asked for — "
            "LIMIT/OFFSET with no ORDER BY slices physical heap order"
        )

    def test_paging_yields_every_user_once_and_in_order(
        self, client, auth_headers, session_factory
    ):
        seeded = _seed_users_descending(session_factory, 40)

        collected = _page_ids(client, auth_headers, "/users", page_size=10)
        returned = [i for i in collected if i in set(seeded)]

        assert len(collected) == len(set(collected)), (
            "a user was delivered on more than one page"
        )
        assert set(seeded) <= set(collected), "a user was delivered on no page at all"
        assert returned == sorted(seeded), (
            "pages are individually fine but do not concatenate in order — "
            "each OFFSET re-slices an undefined order, so the sequence a client "
            "walks is not the sequence the rows are in"
        )


class TestScraperListingOrder:
    def test_listing_is_ordered_by_id(self, client, auth_headers, session_factory):
        seeded = _seed_scrapers_descending(session_factory, 40)

        r = client.get("/scrapers?skip=0&limit=200", headers=auth_headers)
        assert r.status_code == 200, r.text
        returned = [s["id"] for s in r.json() if s["id"] in set(seeded)]

        assert returned == sorted(seeded), (
            "the listing came back in an order the endpoint never asked for"
        )

    def test_paging_yields_every_scraper_once_and_in_order(
        self, client, auth_headers, session_factory
    ):
        seeded = _seed_scrapers_descending(session_factory, 40)

        collected = _page_ids(client, auth_headers, "/scrapers", page_size=10)
        returned = [i for i in collected if i in set(seeded)]

        assert len(collected) == len(set(collected)), (
            "a scraper was delivered on more than one page"
        )
        assert set(seeded) <= set(collected), "a scraper was delivered on no page at all"
        assert returned == sorted(seeded), (
            "pages are individually fine but do not concatenate in order"
        )
