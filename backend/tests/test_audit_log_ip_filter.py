"""The audit log can be asked what came from one address (#378).

The first incident tabletop had one solid pivot, an unfamiliar address in the
container log, and no way to ask the audit log what else it had done. These
tests hold the answer to that question on every surface that returns it (the
list, the CSV export and the counters) and assert on content: which rows came
back, not only that something did.

A filter that silently matches nothing is the failure that matters most here,
because "no rows" is also the answer a harmless address gives. So a malformed
address is a 422, and an IPv6 address matches however it is written.
"""
import csv
import io

from backend import models

SUSPECT = "203.0.113.7"
OTHER = "198.51.100.23"


def _add(db_session, ip: str | None, action: str = "UPDATE", username: str = "alice") -> models.AuditLog:
    entry = models.AuditLog(
        action=action,
        entity_type="entity",
        endpoint="/entities/1",
        method="PUT",
        username=username,
        ip_address=ip,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _seed(db_session) -> None:
    _add(db_session, SUSPECT, action="UPDATE", username="alice")
    _add(db_session, SUSPECT, action="DELETE", username="alice")
    _add(db_session, SUSPECT, action="UPDATE", username="bob")
    _add(db_session, OTHER, action="UPDATE", username="alice")
    _add(db_session, None, action="CREATE", username="carol")


def test_list_returns_only_what_came_from_the_address(client, auth_headers, db_session):
    _seed(db_session)

    resp = client.get(f"/audit-log?ip_address={SUSPECT}", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert {item["ip_address"] for item in body["items"]} == {SUSPECT}
    assert sorted(item["action"] for item in body["items"]) == ["DELETE", "UPDATE", "UPDATE"]


def test_address_combines_with_the_other_filters(client, auth_headers, db_session):
    _seed(db_session)

    resp = client.get(f"/audit-log?ip_address={SUSPECT}&username=alice", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["total"] == 2
    assert all(item["username"] == "alice" for item in resp.json()["items"])


def test_a_malformed_address_is_an_error_not_an_empty_answer(client, auth_headers, db_session):
    """"Nothing came from 203.0.113.700" would read as reassurance."""
    _seed(db_session)

    for bad in ("203.0.113.700", "not-an-ip", "203.0.113.7/24"):
        resp = client.get(f"/audit-log?ip_address={bad}", headers=auth_headers)
        assert resp.status_code == 422, bad
        assert "Not an IP address" in resp.json()["detail"]


def test_an_empty_address_means_no_filter(client, auth_headers, db_session):
    _seed(db_session)

    resp = client.get("/audit-log?ip_address=", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["total"] == 5


def test_ipv6_matches_however_it_is_written(client, auth_headers, db_session):
    """The server records the compressed form; a responder may paste any form."""
    _add(db_session, "2001:db8::1")
    _add(db_session, "2001:db8::2")

    resp = client.get("/audit-log", params={"ip_address": "2001:0DB8:0000:0000::0001"}, headers=auth_headers)

    assert resp.status_code == 200
    assert [item["ip_address"] for item in resp.json()["items"]] == ["2001:db8::1"]


def test_export_is_scoped_to_the_address(client, auth_headers, db_session):
    _seed(db_session)

    resp = client.get(f"/audit-log/export?ip_address={SUSPECT}", headers=auth_headers)

    assert resp.status_code == 200
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert len(rows) == 3
    assert {row["ip_address"] for row in rows} == {SUSPECT}


def test_export_rejects_a_malformed_address(client, auth_headers, db_session):
    resp = client.get("/audit-log/export?ip_address=nope", headers=auth_headers)

    assert resp.status_code == 422


def test_stats_size_what_came_from_the_address(client, auth_headers, db_session):
    _seed(db_session)

    scoped = client.get(f"/audit-log/stats?ip_address={SUSPECT}", headers=auth_headers).json()

    assert scoped["total"] == 3
    assert scoped["by_action"] == {"UPDATE": 2, "DELETE": 1}
    assert {u["username"]: u["count"] for u in scoped["top_users"]} == {"alice": 2, "bob": 1}
    assert sum(day["count"] for day in scoped["last_7_days"]) == 3


def test_stats_without_an_address_still_cover_everything(client, auth_headers, db_session):
    _seed(db_session)

    unscoped = client.get("/audit-log/stats", headers=auth_headers).json()

    assert unscoped["total"] == 5


def test_the_filter_is_admin_only_like_the_rest_of_the_log(client, editor_headers, db_session):
    _seed(db_session)

    for path in ("/audit-log", "/audit-log/export", "/audit-log/stats"):
        resp = client.get(f"{path}?ip_address={SUSPECT}", headers=editor_headers)
        assert resp.status_code == 403, path
