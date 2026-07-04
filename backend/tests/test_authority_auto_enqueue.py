"""Auto-enqueue of authority resolution on ingest (front B) + entity_type filter.

Verifies:
  * ``_distinct_values`` / ``execute_batch_resolution`` can restrict the value
    pool to a single ``entity_type`` (author→person, affiliation→institution).
  * ``enqueue_entity_authority_jobs`` is opt-in, de-duplicated, and stamps the
    right ``entity_type_filter`` into the job params.
"""
from __future__ import annotations

import json

from backend import models
from backend.authority import auto_enqueue
from backend.authority.batch_resolution import (
    VALUE_SOURCE_PUB_AUTHORS,
    _distinct_values,
    _distinct_values_from_publication_attrs,
    execute_batch_resolution,
)


def _entity(db, *, label, entity_type, canonical_id, org_id=None):
    ent = models.RawEntity(
        org_id=org_id, domain="science", entity_type=entity_type,
        primary_label=label, canonical_id=canonical_id,
        attributes_json="{}", validation_status="derived",
        enrichment_status="derived", source="graph_materializer",
    )
    db.add(ent)
    db.flush()
    return ent


def _publication(db, *, title, authors=(), affiliations=(), org_id=None):
    attrs = {
        "author_affiliations": [{"author_name": a, "institutions": []} for a in authors],
        "canonical_affiliations": [{"name": n} for n in affiliations],
    }
    ent = models.RawEntity(
        org_id=org_id, domain="science", entity_type="publication",
        primary_label=title, canonical_id=f"doi:{title}",
        attributes_json=json.dumps(attrs), validation_status="pending",
        enrichment_status="completed", source="openalex",
    )
    db.add(ent)
    db.flush()
    return ent


def _publication_rich(db, *, title, authors, org_id=None):
    """authors: list of (name, orcid, institution)."""
    attrs = {
        "author_affiliations": [
            {
                "author_name": n,
                "author_orcid": orcid,
                "institutions": ([{"name": inst}] if inst else []),
            }
            for (n, orcid, inst) in authors
        ],
    }
    ent = models.RawEntity(
        org_id=org_id, domain="science", entity_type="publication",
        primary_label=title, canonical_id=f"doi:{title}",
        attributes_json=json.dumps(attrs), validation_status="pending",
        enrichment_status="completed", source="openalex",
    )
    db.add(ent)
    db.flush()
    return ent


# ── orcid_hint / affiliation threading ────────────────────────────────────────

def test_publication_author_hints_extracted(db_session):
    from backend.authority.batch_resolution import _publication_author_hints
    _publication_rich(db_session, title="P", authors=[
        ("Ada Lovelace", "0000-0001-0000-0001", "Analytical Engine Lab"),
        ("Grace Hopper", None, "US Navy"),
    ])
    db_session.flush()
    hints = _publication_author_hints(db_session, None)
    assert hints["Ada Lovelace"]["orcid_hint"] == "0000-0001-0000-0001"
    assert hints["Ada Lovelace"]["affiliation"] == "Analytical Engine Lab"
    assert hints["Grace Hopper"]["orcid_hint"] is None
    assert hints["Grace Hopper"]["affiliation"] == "US Navy"


def test_batch_resolution_passes_orcid_hint_per_value(db_session):
    _publication_rich(db_session, title="P", authors=[
        ("Ada Lovelace", "0000-0001-0000-0001", "Analytical Engine Lab"),
    ])
    db_session.flush()
    seen_ctx = {}

    def _fake_resolve(value, entity_type, ctx):
        seen_ctx[value] = (ctx.orcid_hint, ctx.affiliation)
        return []

    execute_batch_resolution(
        db_session, org_id=None, record_org_id=None, field="author",
        entity_type="person", limit=100, skip_existing=False,
        resolve_fn=_fake_resolve, value_source=VALUE_SOURCE_PUB_AUTHORS,
    )
    # orcid_hint is threaded per value; affiliation is intentionally NOT passed
    # (it would dilute an exact-ORCID match via the scorer's affiliation weight).
    assert seen_ctx["Ada Lovelace"][0] == "0000-0001-0000-0001"
    assert seen_ctx["Ada Lovelace"][1] is None


# ── entity_type filtering ─────────────────────────────────────────────────────

def test_distinct_values_filters_by_entity_type(db_session):
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    _entity(db_session, label="Open Lab", entity_type="affiliation", canonical_id="affiliation:ol")
    _entity(db_session, label="Some Paper", entity_type="work", canonical_id="doi:10.1/x")
    db_session.flush()

    authors = _distinct_values(db_session, "primary_label", None, entity_type_filter="author")
    affils = _distinct_values(db_session, "primary_label", None, entity_type_filter="affiliation")

    assert "Ada Lovelace" in authors
    assert "Open Lab" not in authors
    assert "Some Paper" not in authors
    assert affils == ["Open Lab"]


def test_batch_resolution_respects_entity_type_filter(db_session):
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    _entity(db_session, label="Grace Hopper", entity_type="work", canonical_id="doi:10.1/g")
    db_session.flush()

    seen: list[str] = []

    def _fake_resolve(value, entity_type, ctx):
        seen.append(value)
        return []

    summary, _ = execute_batch_resolution(
        db_session, org_id=None, record_org_id=None, field="primary_label",
        entity_type="person", limit=100, skip_existing=False,
        resolve_fn=_fake_resolve, entity_type_filter="author",
    )

    assert seen == ["Ada Lovelace"]  # the 'work' row was excluded
    assert summary["resolved_count"] == 1


# ── enqueue behavior ──────────────────────────────────────────────────────────

def test_enqueue_disabled_by_default(db_session, monkeypatch):
    monkeypatch.delenv("UKIP_AUTO_RESOLVE_ON_INGEST", raising=False)
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    db_session.flush()

    created = auto_enqueue.enqueue_entity_authority_jobs(db_session, org_id=None)

    assert created == []
    assert db_session.query(models.AuthorityResolveJob).count() == 0


def _record(db, *, label, status="pending", org_id=None):
    rec = models.AuthorityRecord(
        org_id=org_id, field_name="primary_label", original_value=label,
        authority_source="orcid", authority_id="A1", canonical_label=label,
        aliases="[]", description="", confidence=0.9, uri=None,
        status=status, resolution_status="exact_match",
        score_breakdown="{}", evidence="[]", merged_sources="[]",
    )
    db.add(rec)
    db.flush()
    return rec


def test_enqueue_creates_two_jobs_when_enabled(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_AUTO_RESOLVE_ON_INGEST", "1")
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    _entity(db_session, label="Open Lab", entity_type="affiliation", canonical_id="affiliation:ol")
    db_session.flush()

    created = auto_enqueue.enqueue_entity_authority_jobs(db_session, org_id=None)

    assert len(created) == 2
    jobs = db_session.query(models.AuthorityResolveJob).all()
    by_type = {j.entity_type: j for j in jobs}
    assert set(by_type) == {"person", "institution"}
    assert json.loads(by_type["person"].params_json)["entity_type_filter"] == "author"
    assert json.loads(by_type["institution"].params_json)["entity_type_filter"] == "affiliation"
    assert json.loads(by_type["person"].params_json)["skip_existing"] is True


def test_enqueue_is_deduplicated(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_AUTO_RESOLVE_ON_INGEST", "1")
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    _entity(db_session, label="Open Lab", entity_type="affiliation", canonical_id="affiliation:ol")
    db_session.flush()

    first = auto_enqueue.enqueue_entity_authority_jobs(db_session, org_id=None)
    second = auto_enqueue.enqueue_entity_authority_jobs(db_session, org_id=None)

    assert len(first) == 2
    assert second == []  # open jobs already exist → no duplicates
    assert db_session.query(models.AuthorityResolveJob).count() == 2


def test_no_job_when_nothing_unresolved(db_session, monkeypatch):
    """Guard: once every label is covered by a record, no no-op job is enqueued."""
    monkeypatch.setenv("UKIP_AUTO_RESOLVE_ON_INGEST", "1")
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    _record(db_session, label="Ada Lovelace", status="confirmed")
    db_session.flush()

    created = auto_enqueue.enqueue_entity_authority_jobs(db_session, org_id=None)

    assert created == []  # author covered, no affiliation rows → nothing to do
    assert db_session.query(models.AuthorityResolveJob).count() == 0


def test_only_unresolved_type_is_enqueued(db_session, monkeypatch):
    """Author has an unresolved label; affiliation is fully covered → person only."""
    monkeypatch.setenv("UKIP_AUTO_RESOLVE_ON_INGEST", "1")
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    _entity(db_session, label="Open Lab", entity_type="affiliation", canonical_id="affiliation:ol")
    _record(db_session, label="Open Lab", status="pending")
    db_session.flush()

    created = auto_enqueue.enqueue_entity_authority_jobs(db_session, org_id=None)

    assert len(created) == 1
    job = db_session.query(models.AuthorityResolveJob).one()
    assert job.entity_type == "person"


# ── publication-attribute value source (OpenAlex path) ────────────────────────

def test_extract_author_names_from_publication_attrs(db_session):
    _publication(db_session, title="Paper A", authors=["Ada Lovelace", "Grace Hopper"],
                 affiliations=["Open Lab"])
    _publication(db_session, title="Paper B", authors=["Ada Lovelace", "Alan Turing"])
    db_session.flush()

    authors = _distinct_values_from_publication_attrs(db_session, None, VALUE_SOURCE_PUB_AUTHORS)

    assert set(authors) == {"Ada Lovelace", "Grace Hopper", "Alan Turing"}  # deduped across pubs


def test_batch_resolution_reads_publication_authors(db_session):
    _publication(db_session, title="Paper A", authors=["Ada Lovelace"])
    db_session.flush()
    seen = []

    def _fake_resolve(value, entity_type, ctx):
        seen.append((value, entity_type))
        return []

    summary, _ = execute_batch_resolution(
        db_session, org_id=None, record_org_id=None, field="author",
        entity_type="person", limit=100, skip_existing=False,
        resolve_fn=_fake_resolve, value_source=VALUE_SOURCE_PUB_AUTHORS,
    )

    assert seen == [("Ada Lovelace", "person")]
    assert summary["resolved_count"] == 1


def test_enqueue_publication_jobs_disabled_by_default(db_session, monkeypatch):
    monkeypatch.delenv("UKIP_AUTO_RESOLVE_ON_INGEST", raising=False)
    _publication(db_session, title="Paper A", authors=["Ada Lovelace"])
    db_session.flush()

    created = auto_enqueue.enqueue_publication_authority_jobs(db_session, org_id=None)

    assert created == []


def test_enqueue_publication_jobs_creates_author_and_affiliation(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_AUTO_RESOLVE_ON_INGEST", "1")
    _publication(db_session, title="Paper A", authors=["Ada Lovelace"], affiliations=["Open Lab"])
    db_session.flush()

    created = auto_enqueue.enqueue_publication_authority_jobs(db_session, org_id=None)

    assert len(created) == 2
    jobs = {j.entity_type: j for j in db_session.query(models.AuthorityResolveJob).all()}
    assert set(jobs) == {"person", "institution"}
    assert jobs["person"].field_name == "author"
    assert json.loads(jobs["person"].params_json)["value_source"] == VALUE_SOURCE_PUB_AUTHORS
    assert jobs["institution"].field_name == "affiliation"


def test_enqueue_publication_jobs_deduplicated(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_AUTO_RESOLVE_ON_INGEST", "1")
    _publication(db_session, title="Paper A", authors=["Ada Lovelace"], affiliations=["Open Lab"])
    db_session.flush()

    first = auto_enqueue.enqueue_publication_authority_jobs(db_session, org_id=None)
    second = auto_enqueue.enqueue_publication_authority_jobs(db_session, org_id=None)

    assert len(first) == 2
    assert second == []


def test_enqueue_publication_jobs_guard_when_all_covered(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_AUTO_RESOLVE_ON_INGEST", "1")
    _publication(db_session, title="Paper A", authors=["Ada Lovelace"])
    db_session.add(models.AuthorityRecord(
        org_id=None, field_name="author", original_value="Ada Lovelace",
        authority_source="orcid", authority_id="A1", canonical_label="Ada Lovelace",
        aliases="[]", description="", confidence=0.9, uri=None, status="confirmed",
        resolution_status="exact_match", score_breakdown="{}", evidence="[]", merged_sources="[]",
    ))
    db_session.flush()

    created = auto_enqueue.enqueue_publication_authority_jobs(db_session, org_id=None)

    # author covered, no affiliations present → nothing to enqueue
    assert created == []
