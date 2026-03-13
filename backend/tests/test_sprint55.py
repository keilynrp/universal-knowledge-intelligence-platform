"""
Sprint 55 — Entity Linker tests.
  GET    /linker/candidates
  POST   /linker/merge
  POST   /linker/dismiss
  GET    /linker/dismissals
  DELETE /linker/dismissals/{id}
"""
import pytest
from sqlalchemy import text

from backend import models


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_entity(db, name, brand, model=None, sku=None):
    e = models.RawEntity(
        entity_name=name,
        brand_capitalized=brand,
        model=model,
        sku=sku,
        enrichment_status="none",
        validation_status="pending",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


# ── Auth guards ───────────────────────────────────────────────────────────────

class TestLinkerAuth:
    def test_candidates_requires_auth(self, client):
        r = client.get("/linker/candidates")
        assert r.status_code == 401

    def test_merge_requires_editor(self, client, viewer_headers):
        r = client.post("/linker/merge", json={"winner_id": 1, "loser_id": 2},
                        headers=viewer_headers)
        assert r.status_code == 403

    def test_dismiss_requires_editor(self, client, viewer_headers):
        r = client.post("/linker/dismiss", json={"entity_a_id": 1, "entity_b_id": 2},
                        headers=viewer_headers)
        assert r.status_code == 403


# ── Candidate detection ───────────────────────────────────────────────────────

class TestCandidates:
    def test_candidates_empty_when_no_entities(self, client, db_session, auth_headers):
        r = client.get("/linker/candidates", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_candidates_finds_similar_pair(self, client, db_session, auth_headers):
        _make_entity(db_session, "Wireless Mouse Pro", "Logitech", model="M720")
        _make_entity(db_session, "Wireless Mouse Pro", "Logitech", model="M720")
        r = client.get("/linker/candidates?threshold=0.8", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert data[0]["score"] >= 0.8
        assert "entity_name" in data[0]["matched_fields"]

    def test_candidates_sorted_by_score_desc(self, client, db_session, auth_headers):
        # Two pairs — one high score, one medium
        _make_entity(db_session, "Keyboard Ultra", "Brand", model="KB100")
        _make_entity(db_session, "Keyboard Ultra", "Brand", model="KB100")   # identical
        _make_entity(db_session, "Keyboard Pro", "Brand", model="KBX")
        _make_entity(db_session, "Keyboard Basic", "Brand", model="KBY")     # lower match
        r = client.get("/linker/candidates?threshold=0.5", headers=auth_headers)
        assert r.status_code == 200
        scores = [item["score"] for item in r.json()]
        assert scores == sorted(scores, reverse=True)


# ── Merge ─────────────────────────────────────────────────────────────────────

class TestMerge:
    def test_merge_winner_absorbs_loser_fields(self, client, db_session, editor_headers):
        winner = _make_entity(db_session, "Pen Drive 64GB", "Kingston", sku=None)
        loser  = _make_entity(db_session, "Pen Drive 64GB", "Kingston", sku="KIN-64")
        r = client.post("/linker/merge",
                        json={"winner_id": winner.id, "loser_id": loser.id},
                        headers=editor_headers)
        assert r.status_code == 200
        result = r.json()
        assert result["id"] == winner.id
        assert result["sku"] == "KIN-64"    # absorbed from loser
        # loser is gone — use a fresh SELECT (get() throws on deleted identity)
        gone = db_session.query(models.RawEntity).filter_by(id=loser.id).first()
        assert gone is None

    def test_merge_same_id_returns_422(self, client, db_session, editor_headers):
        e = _make_entity(db_session, "Thing", "Brand")
        r = client.post("/linker/merge",
                        json={"winner_id": e.id, "loser_id": e.id},
                        headers=editor_headers)
        assert r.status_code == 422

    def test_merge_missing_entity_returns_404(self, client, db_session, editor_headers):
        e = _make_entity(db_session, "Thing", "Brand")
        r = client.post("/linker/merge",
                        json={"winner_id": e.id, "loser_id": 999999},
                        headers=editor_headers)
        assert r.status_code == 404


# ── Dismiss ───────────────────────────────────────────────────────────────────

class TestDismiss:
    def test_dismiss_creates_record(self, client, db_session, editor_headers):
        a = _make_entity(db_session, "Item A", "Brand")
        b = _make_entity(db_session, "Item B", "Brand")
        r = client.post("/linker/dismiss",
                        json={"entity_a_id": a.id, "entity_b_id": b.id},
                        headers=editor_headers)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert "id" in r.json()

    def test_dismiss_is_idempotent(self, client, db_session, editor_headers):
        a = _make_entity(db_session, "Item A", "Brand")
        b = _make_entity(db_session, "Item B", "Brand")
        r1 = client.post("/linker/dismiss",
                         json={"entity_a_id": a.id, "entity_b_id": b.id},
                         headers=editor_headers)
        r2 = client.post("/linker/dismiss",
                         json={"entity_a_id": a.id, "entity_b_id": b.id},
                         headers=editor_headers)
        assert r1.json()["id"] == r2.json()["id"]

    def test_dismissed_pair_not_in_candidates(self, client, db_session, auth_headers, editor_headers):
        a = _make_entity(db_session, "Same Product", "SameBrand", model="X1")
        b = _make_entity(db_session, "Same Product", "SameBrand", model="X1")
        # Dismiss first
        client.post("/linker/dismiss",
                    json={"entity_a_id": a.id, "entity_b_id": b.id},
                    headers=editor_headers)
        r = client.get("/linker/candidates?threshold=0.5", headers=auth_headers)
        assert r.status_code == 200
        ids_in_results = {
            (item["entity_a"]["id"], item["entity_b"]["id"]) for item in r.json()
        }
        pair_a = (min(a.id, b.id), max(a.id, b.id))
        assert pair_a not in ids_in_results

    def test_list_and_undo_dismissal(self, client, db_session, auth_headers, editor_headers):
        a = _make_entity(db_session, "Widget", "ACME")
        b = _make_entity(db_session, "Widget Plus", "ACME")
        dismiss_r = client.post("/linker/dismiss",
                                json={"entity_a_id": a.id, "entity_b_id": b.id},
                                headers=editor_headers)
        dismissal_id = dismiss_r.json()["id"]

        # List
        list_r = client.get("/linker/dismissals", headers=auth_headers)
        assert list_r.status_code == 200
        ids = [d["id"] for d in list_r.json()]
        assert dismissal_id in ids

        # Undo
        del_r = client.delete(f"/linker/dismissals/{dismissal_id}",
                              headers=editor_headers)
        assert del_r.status_code == 204

        # Gone
        list_r2 = client.get("/linker/dismissals", headers=auth_headers)
        ids2 = [d["id"] for d in list_r2.json()]
        assert dismissal_id not in ids2
