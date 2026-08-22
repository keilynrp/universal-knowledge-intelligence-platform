"""The six sentences that quote data must not quote it in Spanish (#209, phase 1b).

Scope is deliberately the **data-composing** strings only — the ones that wrap an
English entity label, concept, provider or relation name in a Spanish sentence,
producing the mixed-language output reported in #209:

    Concentración temática: knowledge graph

The static Spanish sentences in the same modules (`"Output de impacto atípico"`,
the `recommended_action` values) are catalog work and stay Spanish until phase 6.
A section-wide "no Spanish anywhere" assertion belongs at task 6.9, not here —
written now it would be red until the whole catalog lands and would say nothing
about this phase.
"""
import json

from backend import models
from backend.services.pattern_discovery import PatternDiscoveryService
from backend.services.researcher_topic_analytics import _executive_summary
import pytest

pytestmark = pytest.mark.reporting


def _seed(db_session):
    """Entities shaped to trigger every composed-string branch at once.

    Two properties are load-bearing and easy to break by accident:

    - `knowledge graph` must be the outright most common concept. A tie makes
      which cluster wins arbitrary, and the assertion on the concept meaningless.
    - There must be at least two distinct providers, one holding ≥72% of records.
      `_provider_gaps` returns nothing for a single-provider portfolio, so an
      all-`openalex` fixture silently produces no pattern to assert on.
    """
    rows = [
        ("Graph Learning for Research Intelligence", "knowledge graph; AI", 420, 0.91, "openalex"),
        ("Knowledge Graphs and Institutional Analytics", "knowledge graph; analytics", 380, 0.88, "openalex"),
        ("Graph Learning for Research Intelligence", "knowledge graph; AI", 35, 0.34, "openalex"),
        ("Semantic Search for Library Discovery", "semantic search; metadata", 24, 0.41, "openalex"),
        ("Metadata Quality in Research Portfolios", "metadata; authority control", 12, 0.39, "openalex"),
        ("Authority Control for Research Records", "authority control", 8, 0.82, "wos"),
    ]
    entities = []
    for title, concepts, citations, quality, provider in rows:
        entity = models.RawEntity(
            domain="science",
            entity_type="publication",
            primary_label=title,
            enrichment_status="completed",
            enrichment_citation_count=citations,
            enrichment_concepts=concepts,
            enrichment_source=provider,
            quality_score=quality,
            attributes_json=json.dumps({"provider": provider, "keywords": concepts}),
        )
        db_session.add(entity)
        entities.append(entity)
    db_session.commit()
    for target in (entities[1], entities[3], entities[5]):
        db_session.add(models.EntityRelationship(
            source_id=entities[0].id,
            target_id=target.id,
            relation_type="related-to",
            weight=1.0,
        ))
    db_session.commit()
    return entities


def _discover(db_session) -> dict:
    """Discover with the ceiling limit.

    `discover()` ranks patterns and truncates to `limit`, so a low limit makes
    the branches compete: adding one pattern type silently evicts another, and
    a test asserting on the evicted one fails for a reason that has nothing to
    do with language.
    """
    return PatternDiscoveryService.discover(
        db_session, domain_id="science", org_id=None, limit=12
    )


def _by_type(patterns: list[dict], pattern_type: str) -> dict | None:
    return next((p for p in patterns if p["type"] == pattern_type), None)


def _all_by_type(patterns: list[dict], pattern_type: str) -> list[dict]:
    return [p for p in patterns if p["type"] == pattern_type]


# ── pattern_discovery: the four sentences that quote data ────────────────────

def test_semantic_cluster_label_is_english(db_session):
    """The exact string reported in #209: a Spanish label wrapping an English concept."""
    _seed(db_session)

    result = _discover(db_session)
    # Up to three clusters are emitted and then ranked by impact score. Which one
    # ranks first is not this test's business, so assert on all of them.
    clusters = _all_by_type(result["patterns"], "semantic_cluster")

    assert clusters, "fixture did not produce any semantic_cluster pattern"
    for cluster in clusters:
        assert "Concentración temática" not in cluster["label"]
        assert cluster["label"].startswith("Thematic concentration:")

    # The concepts themselves are data — they must survive untranslated.
    concepts = {c["label"].split(":", 1)[1].strip() for c in clusters}
    assert concepts <= {"knowledge graph", "AI", "metadata", "authority control",
                        "analytics", "semantic search"}
    assert "knowledge graph" in concepts, (
        f"the most common seeded concept produced no cluster; got {concepts}"
    )


def test_impact_outlier_evidence_is_english(db_session):
    _seed(db_session)

    result = _discover(db_session)
    outlier = _by_type(result["patterns"], "impact_outlier")

    assert outlier is not None, "fixture did not produce an impact_outlier pattern"
    evidence = outlier["evidence"]
    assert "supera claramente" not in evidence
    assert "línea base" not in evidence
    assert "citas" not in evidence
    assert "citations" in evidence
    # The entity label is data.
    assert "Graph Learning for Research Intelligence" in evidence


def test_provider_gap_evidence_is_english(db_session):
    _seed(db_session)

    result = _discover(db_session)
    gap = _by_type(result["patterns"], "provider_gap")

    assert gap is not None, "fixture did not produce a provider_gap pattern"
    evidence = gap["evidence"]
    assert "registros analizados" not in evidence
    assert "accounts for" in evidence
    assert "openalex" in evidence, "the provider name is data and must survive"
    assert "%" in evidence


def test_collaboration_bridge_evidence_is_english(db_session):
    _seed(db_session)

    result = _discover(db_session)
    bridge = _by_type(result["patterns"], "collaboration_bridge")

    assert bridge is not None, "fixture did not produce a collaboration_bridge pattern"
    evidence = bridge["evidence"]
    # Not a bare "concentra" check — English "concentrates" contains it.
    assert "relaciones" not in evidence
    assert "la relación dominante es" not in evidence
    assert "relationships" in evidence
    # Both the entity label and the relation type are data.
    assert "Graph Learning for Research Intelligence" in evidence
    assert "related-to" in evidence


# ── researcher_topic_analytics: the two headline sentences ───────────────────

def test_topic_headline_is_english_with_evidence():
    """`_executive_summary` is pure, so the composed headline is testable directly."""
    summary = _executive_summary(
        topic="knowledge graph",
        records_analyzed=6,
        ranked=[{"name": "Ada Lovelace", "topic_score": 88, "citation_count": 420}],
    )
    headline = summary["headline"]

    assert "lidera la evidencia sobre" not in headline
    assert "leads the evidence on" in headline
    # Researcher name and topic are both data — they must survive untranslated.
    assert "Ada Lovelace" in headline
    assert "knowledge graph" in headline
    assert "88" in headline


def test_topic_headline_is_english_without_evidence():
    """The empty branch — no ranked researcher clears the bar."""
    summary = _executive_summary(
        topic="quantum biology",
        records_analyzed=0,
        ranked=[],
    )
    headline = summary["headline"]

    assert "No hay suficiente evidencia" not in headline
    assert "Not enough evidence" in headline
    assert "quantum biology" in headline
