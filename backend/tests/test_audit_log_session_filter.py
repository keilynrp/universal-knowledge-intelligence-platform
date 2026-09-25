"""The audit log can be asked what one session did.

Phase 5 of the openspec change ``attribute-and-audit-reads``. Once a session is
known to be hostile, "everything it did" is the next question, reads and
mutations alike. The filter is exact (a session id is opaque) and it scopes the
list, the CSV export and the counters, like ``ip_address`` (#384).
"""
import csv
import io

from backend import models

HOSTILE = "hostile-session-0001"
OTHER = "someone-else-0002"


def _add(db_session, sid: str | None, action: str, ip: str = "203.0.113.7") -> None:
    db_session.add(models.AuditLog(
        action=action, entity_type="entity", endpoint="/entities", method="GET",
        username="alice", user_id=1, session_id=sid, ip_address=ip,
    ))
    db_session.commit()


def _seed(db_session) -> None:
    _add(db_session, HOSTILE, "READ")
    _add(db_session, HOSTILE, "EXPORT")
    _add(db_session, HOSTILE, "UPDATE", ip="198.51.100.23")
    _add(db_session, OTHER, "READ")
    _add(db_session, None, "CREATE")


def test_list_returns_everything_one_session_did(client, auth_headers, db_session):
    _seed(db_session)

    body = client.get(f"/audit-log?session_id={HOSTILE}", headers=auth_headers).json()

    assert body["total"] == 3
    assert {item["session_id"] for item in body["items"]} == {HOSTILE}
    assert sorted(item["action"] for item in body["items"]) == ["EXPORT", "READ", "UPDATE"]


def test_session_and_address_narrow_each_other(client, auth_headers, db_session):
    _seed(db_session)

    body = client.get(f"/audit-log?session_id={HOSTILE}&ip_address=198.51.100.23", headers=auth_headers).json()

    assert [item["action"] for item in body["items"]] == ["UPDATE"]


def test_the_new_actions_are_filterable(client, auth_headers, db_session):
    _seed(db_session)

    body = client.get(f"/audit-log?session_id={HOSTILE}&action=export", headers=auth_headers).json()

    assert [item["action"] for item in body["items"]] == ["EXPORT"]


def test_export_is_scoped_and_carries_the_principal(client, auth_headers, db_session):
    _seed(db_session)

    resp = client.get(f"/audit-log/export?session_id={HOSTILE}", headers=auth_headers)

    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert len(rows) == 3
    assert {row["session_id"] for row in rows} == {HOSTILE}
    assert list(rows[0])[:3] == ["id", "username", "action"], "existing columns keep their positions"


def test_stats_size_what_one_session_did(client, auth_headers, db_session):
    _seed(db_session)

    stats = client.get(f"/audit-log/stats?session_id={HOSTILE}", headers=auth_headers).json()

    assert stats["total"] == 3
    assert stats["by_action"] == {"READ": 1, "EXPORT": 1, "UPDATE": 1}


def test_an_empty_session_filter_means_no_filter(client, auth_headers, db_session):
    _seed(db_session)

    assert client.get("/audit-log?session_id=%20", headers=auth_headers).json()["total"] == 5


def test_the_filter_is_admin_only(client, editor_headers, db_session):
    _seed(db_session)

    for path in ("/audit-log", "/audit-log/export", "/audit-log/stats"):
        assert client.get(f"{path}?session_id={HOSTILE}", headers=editor_headers).status_code == 403, path
