"""Phase 3.5 — bounded backfill of retrospective events from source timestamps.

Backfills journal_metric.computed (nif_updated_at) and authority.accepted
(confirmed_at); verifies bounding, idempotency, and no-duplication against live
emission (which now shares the same source timestamp).
"""
from datetime import datetime, timezone

from backend import models
from backend.scripts.backfill_retrospective_events import run_backfill


_T1 = datetime(2026, 6, 1, 12, 0, 0)


def _events(db, etype=None):
    q = db.query(models.RetrospectiveEvent)
    if etype:
        q = q.filter(models.RetrospectiveEvent.event_type == etype)
    return q.all()


def test_backfills_journal_and_authority(db_session):
    db_session.add(models.JournalMetric(
        org_id=None, issn_l="1111-1111", source_id="S1",
        two_yr_mean_citedness=3.0, normalized_impact_factor=1.2,
        nif_field="Medicine", nif_updated_at=_T1))
    db_session.add(models.AuthorityRecord(
        org_id=None, field_name="author", original_value="v",
        authority_source="orcid", authority_id="0000-0001",
        canonical_label="Jane", confidence=0.9,
        status="confirmed", confirmed_at=_T1))
    db_session.commit()

    result = run_backfill(db_session, org_id=None)
    assert result == {"journal_metric": 1, "authority_accepted": 1}

    jm = _events(db_session, "journal_metric.computed")[0]
    assert jm.occurred_at == _T1
    assert '"backfilled":true' in jm.payload
    acc = _events(db_session, "authority.accepted")[0]
    assert acc.occurred_at == _T1


def test_backfill_is_bounded_to_trustworthy_timestamps(db_session):
    # NIF present but no nif_updated_at → skipped; confirmed but no confirmed_at → skipped.
    db_session.add(models.JournalMetric(
        org_id=None, issn_l="2222-2222", two_yr_mean_citedness=3.0,
        normalized_impact_factor=1.0, nif_updated_at=None))
    db_session.add(models.AuthorityRecord(
        org_id=None, field_name="a", original_value="v",
        status="confirmed", confirmed_at=None))
    db_session.commit()
    result = run_backfill(db_session, org_id=None)
    assert result == {"journal_metric": 0, "authority_accepted": 0}


def test_backfill_is_idempotent(db_session):
    db_session.add(models.JournalMetric(
        org_id=None, issn_l="1111-1111", two_yr_mean_citedness=3.0,
        normalized_impact_factor=1.2, nif_field="Medicine", nif_updated_at=_T1))
    db_session.commit()
    run_backfill(db_session, org_id=None)
    run_backfill(db_session, org_id=None)  # re-run
    assert len(_events(db_session, "journal_metric.computed")) == 1


def test_backfill_does_not_duplicate_live_authority_event(client, auth_headers, db_session, monkeypatch):
    """A record confirmed live then backfilled yields exactly one accepted event."""
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    rec = models.AuthorityRecord(
        org_id=None, field_name="author", original_value="v",
        authority_source="orcid", authority_id="0000-0001",
        canonical_label="Jane", confidence=0.9, status="pending")
    db_session.add(rec)
    db_session.commit()

    resp = client.post(f"/authority/records/{rec.id}/confirm", headers=auth_headers)
    assert resp.status_code == 200
    assert len(_events(db_session, "authority.accepted")) == 1

    # Drop the identity-map cache so backfill reads the committed confirmed_at,
    # as a fresh production session would.
    db_session.expire_all()
    run_backfill(db_session, org_id=None)  # must dedup against the live event
    assert len(_events(db_session, "authority.accepted")) == 1
