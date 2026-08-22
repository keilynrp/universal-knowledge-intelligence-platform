"""Report coverage for authority, coauthorship and journals
(extend-report-module-coverage).

Each section is authored once against the format-neutral payload from
`unify-report-format-coverage`, so the parity guard proves it reached all four
formats. These tests cover the collectors' semantics: what the section says, what
it must never say, and that it never leaks across tenants.
"""
from backend import models, report_builder
from backend.reporting.localize import localize_section
from backend.reporting.section_data import (
    Narrative,
    SectionData,
    StatGrid,
    Table,
)


# ── 1. Authority control ────────────────────────────────────────────────────

def _authority_record(**kw):
    base = dict(
        field_name="brand_capitalized",
        original_value="acme corp",
        canonical_label="ACME Corporation",
        confidence=0.9,
        status="confirmed",
        resolution_status="exact_match",
        review_required=False,
    )
    base.update(kw)
    return models.AuthorityRecord(**base)


def _seed_authority(db, org_id=None) -> None:
    """Two confirmed, three pending review (one ambiguous, two unresolved)."""
    rows = [
        _authority_record(org_id=org_id),
        _authority_record(org_id=org_id, original_value="globex"),
        _authority_record(
            org_id=org_id, original_value="initech", status="pending",
            resolution_status="ambiguous", review_required=True,
            confidence=0.55, nil_reason="multiple_candidates",
        ),
        _authority_record(
            org_id=org_id, original_value="umbrella", status="pending",
            resolution_status="unresolved", review_required=True,
            confidence=0.2, nil_reason="no_candidate_above_threshold",
        ),
        _authority_record(
            org_id=org_id, original_value="soylent", status="pending",
            resolution_status="unresolved", review_required=True,
            confidence=0.1, nil_reason="no_candidate_above_threshold",
        ),
    ]
    for r in rows:
        db.add(r)
    db.commit()


def test_collect_authority_control_reports_counts(db_session):
    """1.1 — total, confirmed and pending-review counts."""
    _seed_authority(db_session)
    section = localize_section(
        report_builder.collect_authority_control(db_session, "default", None)
    )

    assert isinstance(section, SectionData)
    assert section.key == "authority_control"

    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    labels = {i.label: i.value for i in grid.items}
    assert labels["Authority Records"] == "5"
    assert labels["Confirmed"] == "2"
    assert labels["Pending Review"] == "3"
    assert "Mean Confidence" in labels


def test_collect_authority_control_lists_unresolved_conflicts(db_session):
    """1.3 — unresolved conflicts carry their confidence and nil_reason."""
    _seed_authority(db_session)
    section = localize_section(
        report_builder.collect_authority_control(db_session, "default", None)
    )

    tables = [b for b in section.blocks if isinstance(b, Table)]
    conflicts = next(t for t in tables if "Value" in t.columns)
    joined = " ".join(" ".join(r) for r in conflicts.rows)
    assert "initech" in joined
    assert "multiple_candidates" in joined          # nil_reason is surfaced
    assert "no_candidate_above_threshold" in joined
    # confirmed records are not conflicts
    assert "globex" not in joined


def test_collect_authority_control_states_reliability_impact(db_session):
    """1.5 — a review backlog produces a prose reliability statement."""
    _seed_authority(db_session)
    section = localize_section(
        report_builder.collect_authority_control(db_session, "default", None)
    )

    narrative = next(b for b in section.blocks if isinstance(b, Narrative))
    prose = " ".join(narrative.paragraphs).lower()
    assert "3" in " ".join(narrative.paragraphs)    # the backlog size is stated
    assert "review" in prose


def test_collect_authority_control_empty_state_is_explanatory(db_session):
    """1.7 — no records must read as 'not run', never as 'no conflicts found'.

    Absence of authority data is not evidence of clean identity resolution;
    saying so would be a false reassurance in a decision brief.
    """
    section = localize_section(
        report_builder.collect_authority_control(db_session, "default", None)
    )

    narrative = next(b for b in section.blocks if isinstance(b, Narrative))
    prose = " ".join(narrative.paragraphs).lower()
    assert "no authority" in prose or "not been run" in prose or "no records" in prose
    # must NOT claim a clean result
    assert "no conflicts" not in prose


def test_collect_authority_control_is_tenant_scoped(db_session):
    """1.8 — another org's records never appear."""
    _seed_authority(db_session, org_id=1)
    db_session.add(_authority_record(org_id=2, original_value="other-org-secret",
                                     status="pending", resolution_status="unresolved",
                                     review_required=True, confidence=0.3))
    db_session.commit()

    section = localize_section(
        report_builder.collect_authority_control(db_session, "default", 1)
    )
    blob = " ".join(
        " ".join(" ".join(r) for r in b.rows) if isinstance(b, Table)
        else " ".join(b.paragraphs) if isinstance(b, Narrative)
        else " ".join(f"{i.label} {i.value}" for i in b.items)
        for b in section.blocks
    )
    assert "other-org-secret" not in blob
    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    assert {i.label: i.value for i in grid.items}["Authority Records"] == "5"


# ── 2. Readiness caveat in the stakeholder reading ──────────────────────────

def _reading_prose(db, org_id=None) -> str:
    """The prose a reader sees, not the payload a collector returns.

    A collector holds catalog keys; only the render boundary turns them into
    sentences. Asserting on the payload asserted on keys, which is why these
    tests broke the moment the section migrated. Resolving into English here
    keeps the assertions readable AND keeps them true of the report.
    """
    from backend.reporting.localize import localize_section

    section = report_builder.collect_stakeholder_reading(db, "default", org_id)
    section = localize_section(section, "en")
    narrative = next(b for b in section.blocks if isinstance(b, Narrative))
    return " ".join(narrative.paragraphs)


def test_stakeholder_reading_flags_material_authority_backlog(db_session):
    """2.1 — a backlog above threshold adds a caveat to the readiness language."""
    _seed_authority(db_session)          # 3 of 5 pending = 60%
    prose = _reading_prose(db_session)

    assert "3 of 5" in prose or "60%" in prose
    assert "backlog" in prose.lower()
    # the caveat must qualify readiness, not merely mention a number
    assert "not settled" in prose.lower() or "provisional" in prose.lower()


def test_stakeholder_reading_always_discloses_the_observed_ratio(db_session):
    """2.3 — the observed ratio is disclosed whether or not it clears threshold."""
    for record in (
        _authority_record(original_value="a"),
        _authority_record(original_value="b"),
    ):
        db_session.add(record)           # both confirmed → 0% backlog
    db_session.commit()

    prose = _reading_prose(db_session)
    assert "0 of 2" in prose or "0%" in prose


def test_stakeholder_reading_below_threshold_raises_no_caveat(db_session):
    """2.4 — a clean backlog states the ratio but adds no readiness caveat."""
    for record in (
        _authority_record(original_value="a"),
        _authority_record(original_value="b"),
    ):
        db_session.add(record)
    db_session.commit()

    prose = _reading_prose(db_session).lower()
    assert "not settled" not in prose
    assert "material" not in prose


def test_authority_backlog_threshold_is_configurable(db_session, monkeypatch):
    """2.5 — the threshold is configuration, not a buried constant."""
    _seed_authority(db_session)          # 60% backlog

    monkeypatch.setenv("UKIP_REPORT_AUTHORITY_BACKLOG_THRESHOLD", "0.9")
    relaxed = _reading_prose(db_session).lower()
    assert "not settled" not in relaxed  # 60% no longer clears a 90% bar

    monkeypatch.setenv("UKIP_REPORT_AUTHORITY_BACKLOG_THRESHOLD", "0.1")
    strict = _reading_prose(db_session).lower()
    assert "not settled" in strict


# ── 3. Collaboration graph ──────────────────────────────────────────────────

from datetime import datetime, timedelta, timezone  # noqa: E402
import pytest

pytestmark = pytest.mark.reporting


def _seed_coauthorship(db, org_id=None, *, computed_at="now") -> None:
    """Two communities (1: Alice, Bob; 2: Carol, Dave) with a Bob–Carol bridge
    edge across them. Alice is the most central."""
    authors = [
        (1, "alice", "Alice Ng", 1, 5, 0.90, 20),
        (2, "bob", "Bob Ito", 1, 3, 0.50, 10),
        (3, "carol", "Carol Vex", 2, 4, 0.70, 15),
        (4, "dave", "Dave Roe", 2, 2, 0.30, 5),
    ]
    ts = None if computed_at is None else (
        datetime.now(timezone.utc) if computed_at == "now"
        else datetime.now(timezone.utc) - timedelta(days=120)
    )
    for aid, key, name, comm, degree, cent, pubs in authors:
        db.add(models.Author(id=aid, name_key=key, display_name=name))
        db.add(models.AuthorStats(
            author_id=aid, org_id=org_id, domain_id="default",
            degree=degree, centrality=cent, community_id=comm,
            publication_count=pubs, computed_at=ts,
        ))
    edges = [(1, 2), (3, 4), (2, 3)]  # (2,3) crosses communities
    for a, b in edges:
        db.add(models.CoauthorEdge(
            author_a_id=a, author_b_id=b, org_id=org_id,
            domain_id="default", weight=1.0,
        ))
    db.commit()


def test_collect_collaboration_graph_reports_counts(db_session):
    """3.1 — author, edge and community counts."""
    _seed_coauthorship(db_session)
    section = localize_section(
        report_builder.collect_collaboration_graph(db_session, "default", None)
    )

    assert section.key == "collaboration_graph"
    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    labels = {i.label: i.value for i in grid.items}
    assert labels["Authors"] == "4"
    assert labels["Collaborations"] == "3"
    assert labels["Communities"] == "2"


def test_collect_collaboration_graph_lists_most_central(db_session):
    """3.3 — most central authors with degree, centrality, publications."""
    _seed_coauthorship(db_session)
    section = localize_section(
        report_builder.collect_collaboration_graph(db_session, "default", None)
    )

    table = next(t for t in section.blocks if isinstance(t, Table) and "Centrality" in t.columns)
    assert table.rows[0][0] == "Alice Ng"          # highest centrality leads
    joined = " ".join(" ".join(r) for r in table.rows)
    assert "Bob Ito" in joined and "Carol Vex" in joined


def test_collect_collaboration_graph_identifies_bridges(db_session):
    """3.5 — bridge authors spanning communities are identified."""
    _seed_coauthorship(db_session)
    section = localize_section(
        report_builder.collect_collaboration_graph(db_session, "default", None)
    )

    tables = [t for t in section.blocks if isinstance(t, Table)]
    bridges = next(t for t in tables if "Bridges" in t.columns[0] or "bridge" in t.columns[0].lower())
    names = " ".join(" ".join(r) for r in bridges.rows)
    # Bob (comm 1) and Carol (comm 2) are the endpoints of the cross-community edge
    assert "Bob Ito" in names and "Carol Vex" in names
    assert "Dave Roe" not in names                 # Dave has no cross-community edge


def test_collect_collaboration_graph_issues_no_graph_computation(db_session, monkeypatch):
    """3.7 — rendering reads precomputed stats; it must not recompute the graph."""
    _seed_coauthorship(db_session)

    import backend.coauthorship.recompute as recompute_mod
    import backend.graph_analytics as ga

    def _boom(*a, **k):
        raise AssertionError("collaboration_graph invoked the graph analytics path")

    monkeypatch.setattr(recompute_mod, "recompute_coauthor_stats", _boom)
    monkeypatch.setattr(ga, "detect_communities", _boom)
    monkeypatch.setattr(ga, "pagerank", _boom)

    section = localize_section(
        report_builder.collect_collaboration_graph(db_session, "default", None)
    )
    assert section.key == "collaboration_graph"     # rendered without recomputation


def test_collect_collaboration_graph_flags_staleness(db_session):
    """3.8 — a stale computed_at raises a staleness notice.

    (`AuthorStats.computed_at` defaults to now() at insert, so 'absent' is a
    legacy-row case not reproducible through the constructor; the stale path is
    the one a live workspace actually hits.)
    """
    _seed_coauthorship(db_session, computed_at="stale")   # 120 days old
    section = localize_section(
        report_builder.collect_collaboration_graph(db_session, "default", None)
    )

    narrative = next(b for b in section.blocks if isinstance(b, Narrative))
    assert "stale" in " ".join(narrative.paragraphs).lower()


def test_collect_collaboration_graph_empty_state(db_session):
    """3.9 — no author stats → explanatory empty state."""
    section = localize_section(
        report_builder.collect_collaboration_graph(db_session, "default", None)
    )
    narrative = next(b for b in section.blocks if isinstance(b, Narrative))
    prose = " ".join(narrative.paragraphs).lower()
    assert "coauthorship" in prose or "collaboration" in prose
    assert "not" in prose                           # "has not been run" / "no author..."


def test_collect_collaboration_graph_is_tenant_scoped(db_session):
    """3.10 — another org's authors never appear."""
    _seed_coauthorship(db_session, org_id=1)
    db_session.add(models.Author(id=99, name_key="secret", display_name="Secret Author"))
    db_session.add(models.AuthorStats(
        author_id=99, org_id=2, domain_id="default",
        degree=9, centrality=0.99, community_id=7, publication_count=99,
        computed_at=datetime.now(timezone.utc),
    ))
    db_session.commit()

    section = localize_section(
        report_builder.collect_collaboration_graph(db_session, "default", 1)
    )
    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    assert {i.label: i.value for i in grid.items}["Authors"] == "4"
    blob = " ".join(
        " ".join(" ".join(r) for r in b.rows) if isinstance(b, Table) else ""
        for b in section.blocks
    )
    assert "Secret Author" not in blob


# ── 4. Journal portfolio ────────────────────────────────────────────────────

def _seed_journals(db, org_id=None) -> None:
    rows = [
        # display, nif, nif_field, bayes, ci_low, ci_high, works_2yr, apc, doaj
        ("Nature Methods", 4.20, "biology", 4.05, 3.60, 4.55, 40, 11690, True),
        ("Open Data J",    1.80, "cs",      1.75, 1.30, 2.25, 12, 0,     True),
        # A journal with a Bayesian point estimate but NO credible interval:
        # its estimate must never be shown bare.
        ("Sparse Journal", 0.90, "physics", 2.50, None, None, 3, 3000, False),
    ]
    for display, nif, field, bayes, lo, hi, works, apc, doaj in rows:
        db.add(models.JournalMetric(
            org_id=org_id, issn_l=f"issn-{display[:4]}", display_name=display,
            normalized_impact_factor=nif, nif_field=field,
            nif_bayes=bayes, nif_ci_low=lo, nif_ci_high=hi,
            works_2yr=works, apc_usd=apc, is_in_doaj=doaj,
        ))
    db.commit()


def _journal_section(db, org_id=None):
    # Localized: since issue 268 the collector emits catalog keys and the
    # renderer resolves them. These tests identify columns by their visible name
    # ("Bayes" in the header), which is the level a reader checks at — asserting
    # on keys instead would stop catching two keys that render the same text.
    return localize_section(
        report_builder.collect_journal_portfolio(db, "default", org_id)
    )


def test_collect_journal_portfolio_reports_distribution(db_session):
    """4.1 — distinct journals, DOAJ share and APC exposure."""
    _seed_journals(db_session)
    section = _journal_section(db_session)

    assert section.key == "journal_portfolio"
    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    labels = {i.label: i.value for i in grid.items}
    assert labels["Journals"] == "3"
    assert "67%" in labels["In DOAJ"] or "2 of 3" in (labels["In DOAJ"] + (next(i.sub for i in grid.items if i.label == "In DOAJ") or ""))


def test_journal_bayes_never_renders_without_its_interval(db_session):
    """4.3 — nif_bayes never appears without [ci_low, ci_high]."""
    _seed_journals(db_session)
    section = _journal_section(db_session)
    table = next(t for t in section.blocks if isinstance(t, Table) and any("Bayes" in c for c in t.columns))
    bayes_col = next(i for i, c in enumerate(table.columns) if "Bayes" in c)

    by_name = {row[0]: row for row in table.rows}
    # journal with an interval → estimate and both bounds appear, bound together
    nature = by_name["Nature Methods"][bayes_col]
    assert "4.05" in nature and "3.60" in nature and "4.55" in nature
    # journal whose interval is missing → estimate is NOT shown bare
    sparse = by_name["Sparse Journal"][bayes_col]
    assert "2.5" not in sparse                      # the bare point estimate never leaks


def test_journal_nif_labelled_as_field_normalized_not_jif(db_session):
    """4.5 — NIF is labelled a field-normalized open proxy, never a JIF.

    This used to ban the string outright. It cannot any more: since the method
    footer renders inside the section (report-presentation 5.1), the section
    carries a disclosure the contract *requires* — "a proxy metric names what it
    is not" — and naming what it is not means writing the term.

    So the assertion tests the intent instead of the string: every mention of the
    better-known measure must sit in a negation. A bare mention would be exactly
    the claim the ban was there to prevent.
    """
    _seed_journals(db_session)
    html = report_builder._section_journal_portfolio(db_session, "default", None)
    lower = html.lower()
    assert "field-normalized" in lower

    for term in ("impact factor", "jif"):
        start = 0
        while (idx := lower.find(term, start)) != -1:
            preceding = lower[max(0, idx - 70):idx]
            assert "not" in preceding, (
                f"{term!r} is stated affirmatively of this figure: "
                f"...{preceding}[{term}]..."
            )
            start = idx + len(term)


def test_journal_works_2yr_labelled_local(db_session):
    """4.6 — works_2yr is labelled as local coverage."""
    _seed_journals(db_session)
    html = report_builder._section_journal_portfolio(db_session, "default", None).lower()
    assert "local" in html


def test_collect_journal_portfolio_empty_state(db_session):
    """4.7 — no journal metrics → explanatory empty state."""
    section = _journal_section(db_session)
    narrative = next(b for b in section.blocks if isinstance(b, Narrative))
    assert "journal" in " ".join(narrative.paragraphs).lower()


def test_collect_journal_portfolio_is_tenant_scoped(db_session):
    """4.8 — another org's journals never appear."""
    _seed_journals(db_session, org_id=1)
    db_session.add(models.JournalMetric(
        org_id=2, issn_l="issn-secret", display_name="Secret Journal",
        normalized_impact_factor=9.9, nif_field="x", works_2yr=1, is_in_doaj=False,
    ))
    db_session.commit()

    section = _journal_section(db_session, org_id=1)
    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    assert {i.label: i.value for i in grid.items}["Journals"] == "3"
    blob = " ".join(
        " ".join(" ".join(r) for r in b.rows) if isinstance(b, Table) else ""
        for b in section.blocks
    )
    assert "Secret Journal" not in blob


# ── Section-count ceiling ───────────────────────────────────────────────────

def test_every_public_section_can_be_requested_at_once(client, auth_headers):
    """The request cap must accommodate the whole published vocabulary.

    The picker selects every section by default, so a cap below the number of
    public sections turns "select all + export" into a 422. Pydantic does not
    validate field defaults, so this only breaks for real callers — which is
    exactly why it needs an explicit test rather than trusting the default.
    """
    from backend.routers.reports import _PUBLIC_REPORT_SECTIONS

    resp = client.post(
        "/reports/generate",
        json={"domain_id": "default", "sections": list(_PUBLIC_REPORT_SECTIONS)},
        headers=auth_headers,
    )
    assert resp.status_code == 200, (
        f"requesting all {len(_PUBLIC_REPORT_SECTIONS)} public sections failed: "
        f"{resp.text[:300]}"
    )
