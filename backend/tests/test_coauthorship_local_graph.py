"""Tests for local-graph coauthor sourcing (Task 7 wiring completion).

The coauthorship scoring signal was implemented but inert because no source
populated collaborator sets. These tests cover `local_coauthor_names` (and the
provider factory) which traverse the local CoauthorEdge graph so the resolver
can finally feed real overlap into the scoring engine.
"""
from __future__ import annotations

from backend import models
from backend.authority.coauthorship_signal import (
    local_coauthor_names,
    make_local_coauthor_provider,
)
from backend.coauthorship.identity import name_key


def _author(db, display_name: str) -> models.Author:
    a = models.Author(name_key=name_key(display_name), display_name=display_name)
    db.add(a)
    db.flush()
    return a


def _edge(db, a: models.Author, b: models.Author, *, org_id=0, domain_id="science", weight=1):
    db.add(models.CoauthorEdge(
        author_a_id=a.id, author_b_id=b.id, org_id=org_id, domain_id=domain_id, weight=weight,
    ))


def test_returns_neighbor_display_names(db_session):
    smith = _author(db_session, "John Smith")
    jones = _author(db_session, "Mary Jones")
    lee = _author(db_session, "Wei Lee")
    _edge(db_session, smith, jones)
    _edge(db_session, lee, smith)  # reverse direction also counts
    db_session.commit()

    names = local_coauthor_names(db_session, "John Smith", org_id=0, domain_id="science")
    assert set(names) == {"Mary Jones", "Wei Lee"}


def test_unknown_author_returns_empty(db_session):
    assert local_coauthor_names(db_session, "Nobody Here", org_id=0, domain_id="science") == []


def test_author_without_edges_returns_empty(db_session):
    _author(db_session, "Lonely Author")
    db_session.commit()
    assert local_coauthor_names(db_session, "Lonely Author", org_id=0, domain_id="science") == []


def test_lookup_is_name_key_insensitive(db_session):
    smith = _author(db_session, "John Smith")
    jones = _author(db_session, "Mary Jones")
    _edge(db_session, smith, jones)
    db_session.commit()
    # Different surface form, same name_key, should still resolve.
    names = local_coauthor_names(db_session, "Smith, John", org_id=0, domain_id="science")
    assert "Mary Jones" in names


def test_domain_scoping_excludes_other_domains(db_session):
    smith = _author(db_session, "John Smith")
    jones = _author(db_session, "Mary Jones")
    _edge(db_session, smith, jones, domain_id="healthcare")
    db_session.commit()
    assert local_coauthor_names(db_session, "John Smith", org_id=0, domain_id="science") == []
    assert local_coauthor_names(db_session, "John Smith", org_id=0, domain_id="healthcare") == ["Mary Jones"]


def test_provider_factory_resolves_by_name(db_session):
    smith = _author(db_session, "John Smith")
    jones = _author(db_session, "Mary Jones")
    _edge(db_session, smith, jones)
    db_session.commit()
    provider = make_local_coauthor_provider(db_session, org_id=0, domain_id="science")
    assert provider("John Smith") == ["Mary Jones"]
    assert provider("Unknown Person") == []


# ── End-to-end: provider drives the resolver's coauthorship signal ────────────

def test_resolver_uses_provider_to_boost_score(monkeypatch):
    from backend.authority import resolver as resolver_mod
    from backend.authority.base import AuthorityCandidate, ResolveContext

    candidate = AuthorityCandidate(
        authority_source="openalex",
        authority_id="A1",
        canonical_label="John Smith",
        description="MIT",
    )

    class _FakeResolver:
        source_name = "openalex"

        def resolve(self, value, entity_type):
            return [
                AuthorityCandidate(
                    authority_source="openalex",
                    authority_id="A1",
                    canonical_label="John Smith",
                    description="MIT",
                )
            ]

    monkeypatch.setattr(resolver_mod, "_RESILIENT", [_FakeResolver()])
    # Bypass the resolver cache so each call returns *fresh* candidate objects
    # (cached objects are scored in-place and would be shared across both calls).
    monkeypatch.setattr(
        resolver_mod.get_resolver_cache(),
        "get_or_load",
        lambda source, value, entity_type, loader: loader(),
    )

    query_coauthors = ["Mary Jones", "Wei Lee"]
    # Provider returns a fully-overlapping collaborator set for the candidate.
    provider = lambda label: ["Mary Jones", "Wei Lee"]

    with_signal = resolver_mod.resolve_all(
        "J Smith", "person",
        ResolveContext(coauthors=query_coauthors, candidate_coauthor_provider=provider),
    )
    without_signal = resolver_mod.resolve_all("J Smith", "person", ResolveContext())

    assert with_signal[0].confidence > without_signal[0].confidence
    assert with_signal[0].score_breakdown["coauthorship"] == 1.0
