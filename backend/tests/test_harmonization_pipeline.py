"""Functional coverage for the harmonization pipeline (steps metadata + a full
preview -> apply -> undo cycle)."""
from backend import models


def _seed_dirty_label(db_session) -> int:
    entity = models.RawEntity(
        primary_label="  Messy   Label  ",
        entity_type="Organization",
        domain="science",
        validation_status="pending",
    )
    db_session.add(entity)
    db_session.commit()
    return entity.id


def test_steps_expose_order_and_reversible_flags(client, auth_headers):
    resp = client.get("/harmonization/steps", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    steps = resp.json()["steps"]
    assert [s["order"] for s in steps] == list(range(1, len(steps) + 1))
    by_id = {s["step_id"]: s for s in steps}
    # set_default_validation is undoable via change records, so it must advertise it.
    assert by_id["set_default_validation"]["reversible"] is True


def test_preview_apply_undo_cycle_normalizes_and_restores(client, auth_headers, db_session):
    entity_id = _seed_dirty_label(db_session)

    preview = client.post("/harmonization/preview/normalize_labels", headers=auth_headers)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["total_affected"] >= 1
    assert any(c["record_id"] == entity_id for c in body["sample_changes"])

    apply = client.post("/harmonization/apply/normalize_labels", headers=auth_headers)
    assert apply.status_code == 200, apply.text
    log_id = apply.json()["log_id"]
    assert apply.json()["records_updated"] >= 1

    db_session.expire_all()
    cleaned = db_session.get(models.RawEntity, entity_id)
    assert cleaned.primary_label == "Messy Label"

    undo = client.post(f"/harmonization/undo/{log_id}", headers=auth_headers)
    assert undo.status_code == 200, undo.text
    assert undo.json()["records_restored"] >= 1

    db_session.expire_all()
    restored = db_session.get(models.RawEntity, entity_id)
    assert restored.primary_label == "  Messy   Label  "
