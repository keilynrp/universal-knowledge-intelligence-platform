"""The admin POST /journals/normalize must scope to the caller's org the SAME
way the journal READ endpoints do (via resolve_request_org_id), not normalize
across all orgs. The bug surfaces for a legacy admin whose user.org_id is None:
reads scope them to LEGACY_GLOBAL_ORG_ID (-1) but the raw-org_id write path
treated None as "all orgs"."""
from uuid import uuid4

from backend import models
from backend.auth import create_access_token
from backend.tenant_access import LEGACY_GLOBAL_ORG_ID


def _make_admin(session_factory, *, with_org: bool):
    suffix = uuid4().hex[:8]
    username = f"norm_admin_{suffix}"
    with session_factory() as db:
        user = models.User(
            username=username, password_hash="test-hash", role="admin", is_active=True
        )
        db.add(user)
        db.flush()
        org_id = None
        if with_org:
            org = models.Organization(
                name=f"Org {suffix}", slug=f"org-{suffix}",
                owner_id=user.id, plan="pro", is_active=True,
            )
            db.add(org)
            db.flush()
            db.add(models.OrganizationMember(org_id=org.id, user_id=user.id, role="owner"))
            user.org_id = org.id
            org_id = org.id
        db.commit()
    token = create_access_token(subject=username, role="admin")
    return {"headers": {"Authorization": f"Bearer {token}"}, "org_id": org_id}


def test_legacy_admin_normalize_scopes_to_legacy_org(client, session_factory, db_session):
    """A legacy admin (no org) must only normalize LEGACY_GLOBAL_ORG_ID rows,
    NOT another org's rows — matching how their reads are scoped."""
    legacy_admin = _make_admin(session_factory, with_org=False)

    # Two rows in the legacy global org (so a median exists) + one in another org.
    db_session.add(models.JournalMetric(
        org_id=LEGACY_GLOBAL_ORG_ID, issn_l="L1", two_yr_mean_citedness=2.0, nif_field="X"))
    db_session.add(models.JournalMetric(
        org_id=LEGACY_GLOBAL_ORG_ID, issn_l="L2", two_yr_mean_citedness=6.0, nif_field="X"))
    db_session.add(models.JournalMetric(
        org_id=5, issn_l="OTHER", two_yr_mean_citedness=100.0, nif_field="X"))
    db_session.commit()

    resp = client.post("/journals/normalize", headers=legacy_admin["headers"])
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2  # only the two legacy-org rows

    rows = {r.issn_l: r for r in db_session.query(models.JournalMetric).all()}
    assert rows["L1"].normalized_impact_factor is not None
    assert rows["L2"].normalized_impact_factor is not None
    assert rows["OTHER"].normalized_impact_factor is None  # other org untouched


def test_org_scoped_admin_normalize_only_touches_own_org(client, session_factory, db_session):
    """Regression guard: an org-scoped admin only normalizes their own org."""
    org_a = _make_admin(session_factory, with_org=True)
    org_b = _make_admin(session_factory, with_org=True)

    db_session.add(models.JournalMetric(
        org_id=org_a["org_id"], issn_l="A1", two_yr_mean_citedness=2.0, nif_field="X"))
    db_session.add(models.JournalMetric(
        org_id=org_a["org_id"], issn_l="A2", two_yr_mean_citedness=6.0, nif_field="X"))
    db_session.add(models.JournalMetric(
        org_id=org_b["org_id"], issn_l="B1", two_yr_mean_citedness=10.0, nif_field="X"))
    db_session.commit()

    resp = client.post("/journals/normalize", headers=org_a["headers"])
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    rows = {r.issn_l: r for r in db_session.query(models.JournalMetric).all()}
    assert rows["A1"].normalized_impact_factor is not None
    assert rows["B1"].normalized_impact_factor is None  # org B untouched
