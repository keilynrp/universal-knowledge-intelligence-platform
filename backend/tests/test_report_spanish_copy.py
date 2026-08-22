"""A Spanish report renders Spanish copy, not English that resolved cleanly.

`test_report_render_boundary.py` says this in its own docstring: it catches an
unresolved KEY, not untranslated English, and a key replaced by an English
literal keeps it green. That is exactly how the stakeholder reading shipped —
its copy moved into the catalog in #284, every key resolved without leaking,
and the whole section still rendered in English because the renderer was never
told which language to resolve into.

So this asserts the complement, and does it from the catalog rather than from
hardcoded sentences: for each migrated key, the Spanish copy must appear in a
Spanish report and the English copy must not. Hardcoding the sentences would
make the test pass on a wording it agrees with rather than on the catalog the
report actually reads.

Params are stripped before comparison — `translate()` substitutes them, so the
rendered text contains numbers where the catalog holds `{placeholders}`. What
both sides share is the literal text between placeholders; the longest such run
is the anchor, because several of these sentences open with a placeholder and
would otherwise anchor on the empty string.

**Two cases corroborate rather than isolate.** The authority backlog sentence is
a strict substring of the stakeholder one — deliberately, they say the same
thing — so no anchor can distinguish them by searching the whole document.
Dropping the language argument makes both fail, and the stakeholder section is
the culprit in each. Read a failure in `report.narrative.authority.backlog.*`
as "one of these two sections is wrong", not as a location.

Mutation-checked: removing `language=` from the stakeholder call in `build()`
fails two of these cases. It leaves `test_report_render_boundary.py` entirely
green, which is the gap this file exists to close.
"""

from __future__ import annotations

import re

import pytest

from backend import models, report_builder
from backend.i18n.catalog import translate

pytestmark = pytest.mark.reporting

#: Sections needed for the keys below to render at all. Two of them —
#: topic_clusters and collaboration_graph — are absent from the render-boundary
#: guard's own list, which is why nothing checked their copy until now.
_SECTIONS = [
    "entity_stats",
    "enrichment_coverage",
    "impact_projection",
    "authority_control",
    "topic_clusters",
    "collaboration_graph",
]

#: Keys this batch migrated, each of which renders with the fixture below.
_MIGRATED = [
    "report.takeaway.enrichment_coverage",
    "report.method.topic_clusters",
    "report.takeaway.impact",
    "report.stat.impact.sub.range",
    "report.stat.impact.sub.stability",
    "report.narrative.authority.backlog.other",
    "report.narrative.authority.provisional",
    "report.stakeholder.identity_backlog.other",
]


def _literal_anchor(key: str, language: str) -> str:
    """The longest run of literal text in a catalog entry.

    Not the leading run: several of these sentences open with a placeholder
    ("{count} de {total} registros …"), where a prefix is the empty string and
    an assertion on it passes against any output at all. The longest segment
    between placeholders is both non-empty and distinctive, and it is free of
    the substitution that makes a rendered sentence differ from its catalog
    form.
    """
    segments = re.split(r"\{[^}]*\}", translate(key, language))
    return max(segments, key=len).strip()


def _seed(db) -> None:
    for idx in range(4):
        db.add(models.RawEntity(
            primary_label=f"Record {idx}", domain="default",
            validation_status="valid" if idx else "pending",
            enrichment_status="completed",
            enrichment_concepts="knowledge graph; ontology",
            enrichment_citation_count=100 + idx,
            enrichment_source="openalex",
            secondary_label="Review",
            quality_score=0.8,
        ))
    # `pending` counts review_required, not status — seeding status alone leaves
    # the branch that carries the reliability prose unreached, and the test
    # passes without ever rendering what it claims to check.
    for idx in range(3):
        db.add(models.AuthorityRecord(
            org_id=None, field_name="primary_label",
            original_value=f"Record {idx}", authority_source="wikidata",
            authority_id=f"Q{idx}", canonical_label=f"Canonical {idx}",
            confidence=0.30 + idx / 100, status="pending",
            resolution_status="ambiguous", review_required=True,
        ))
    db.commit()


@pytest.fixture
def spanish_report(db_session) -> str:
    _seed(db_session)
    return report_builder.build(
        db_session, "default", _SECTIONS, org_id=None, language="es"
    )


@pytest.mark.parametrize("key", _MIGRATED)
def test_the_spanish_copy_is_what_renders(spanish_report, key):
    spanish = _literal_anchor(key, "es")
    assert spanish, f"{key} has no literal text to anchor on"
    assert spanish in spanish_report, (
        f"{key} did not render its Spanish copy. The key resolved — the "
        f"render-boundary guard would not see this — but into the wrong "
        f"language.\nExpected to find: {spanish!r}"
    )


@pytest.mark.parametrize("key", _MIGRATED)
def test_the_english_copy_does_not_survive(spanish_report, key):
    english = _literal_anchor(key, "en")
    spanish = _literal_anchor(key, "es")
    if english == spanish:
        pytest.skip(f"{key} reads identically in both languages")
    assert english not in spanish_report, (
        f"{key} rendered its English copy inside a Spanish report.\n"
        f"Found: {english!r}"
    )
