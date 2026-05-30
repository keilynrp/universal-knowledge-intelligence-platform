"""Server-side pagination for disambiguation grouping (Phase 1, Task 4).

The /disambiguate/{field} endpoint must accept skip/limit, page the group list
server-side, and report the full group count via X-Total-Count + total_groups.
"""
import pytest

from backend import models


@pytest.fixture
def seeded_variation_groups(db_session):
    """Insert >=12 near-duplicate clusters so grouping yields many groups."""
    rows = []
    for i in range(14):
        base = f"Globex Industries {i}"
        # three lexical variations per cluster -> one group each
        rows.append(models.RawEntity(primary_label=base))
        rows.append(models.RawEntity(primary_label=base + "  "))
        rows.append(models.RawEntity(primary_label=base.replace("Industries", "industries")))
    db_session.add_all(rows)
    db_session.commit()
    return 14


def test_disambiguate_paginates_and_reports_total(
    client, auth_headers, seeded_variation_groups
):
    res = client.get(
        "/disambiguate/primary_label?threshold=80&skip=0&limit=5",
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["groups"]) <= 5
    assert body["total_groups"] >= len(body["groups"])
    assert res.headers["X-Total-Count"] == str(body["total_groups"])


def test_disambiguate_second_page_differs(client, auth_headers, seeded_variation_groups):
    page1 = client.get(
        "/disambiguate/primary_label?threshold=80&skip=0&limit=3", headers=auth_headers
    ).json()["groups"]
    page2 = client.get(
        "/disambiguate/primary_label?threshold=80&skip=3&limit=3", headers=auth_headers
    ).json()["groups"]
    mains1 = {g["main"] for g in page1}
    mains2 = {g["main"] for g in page2}
    assert mains1.isdisjoint(mains2)
