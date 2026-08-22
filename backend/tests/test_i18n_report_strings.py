"""Report-surface strings come from the catalog, not from literals.

Phase 6 group A. These modules feed generated reports, which default to English
by decision (2026-07-31) and ignore `Accept-Language`, so migrating them changes
nothing a reader sees today — it moves the text into the catalog so phase 8 can
select a language.

The tests assert two separable things:

* the rendered output is **English**, which is the observable change;
* the text **came from the catalog**, which is the point of the migration.

The second needs its own assertion. A module that simply had its Spanish
literals rewritten in English would satisfy the first and none of the intent, so
each module is also exercised with the catalog monkeypatched — if the output
does not follow, the call site is still hard-coded.
"""

from pathlib import Path

import pytest

from backend.i18n import catalog as catalog_module
from backend.services.impact_projection import ImpactProjectionService

pytestmark = pytest.mark.reporting

#: The service reads `kpis` / `quality` / `top_entities`, not flat fields. A flat
#: fixture yields `total_entities == 0` and silently takes the empty branch, so a
#: test claiming to exercise a populated portfolio would exercise neither.
_SNAPSHOT_STRONG = {
    "domain_id": 1,
    "kpis": {"total_entities": 500, "enrichment_pct": 96.0, "avg_citations": 40.0},
    "quality": {"average": 0.92},
    "top_entities": [{"id": i, "citation_count": 400 - i} for i in range(10)],
}
_SNAPSHOT_EMPTY = {"kpis": {"total_entities": 0}, "quality": {}, "top_entities": []}

_SPANISH_MARKERS = (
    "proyección",
    "portafolio",
    "Importa",
    "enriquece",
    "señal",
    "línea base",
    "brechas",
    "supuestos",
    "registros",
)


def _projection_text(snapshot: dict) -> str:
    result = ImpactProjectionService.build_from_snapshot(snapshot)
    return " ".join(
        str(result.get(field, "")) for field in ("recommendation", "brief_angle", "explanation")
    )


class TestImpactProjectionIsEnglish:
    @pytest.mark.parametrize(
        "snapshot,label", [(_SNAPSHOT_STRONG, "populated"), (_SNAPSHOT_EMPTY, "empty")]
    )
    def test_no_spanish_remains(self, snapshot, label):
        text = _projection_text(snapshot)

        found = [marker for marker in _SPANISH_MARKERS if marker.lower() in text.lower()]
        assert not found, f"the {label} projection still reads Spanish: {found} in {text!r}"

    def test_every_field_is_populated(self):
        """A migration that silently emptied a field would pass a Spanish check."""
        result = ImpactProjectionService.build_from_snapshot(_SNAPSHOT_STRONG)

        for field in ("recommendation", "brief_angle", "explanation"):
            assert result.get(field), f"{field} is empty after the migration"


class TestImpactProjectionReadsTheCatalog:
    """The assertion that distinguishes migration from translation-in-place."""

    def test_output_follows_the_catalog(self, monkeypatch):
        sentinel = "SENTINEL-FROM-CATALOG"
        # Captured before patching: inside the replacement, the attribute is the
        # replacement itself and the real loader is no longer reachable.
        real_keys = [
            key
            for key in catalog_module._load_catalog.__wrapped__("en")
            if key.startswith("report.impact_projection.")
        ]
        monkeypatch.setattr(
            catalog_module,
            "_load_catalog",
            lambda language: {key: sentinel for key in real_keys},
        )

        text = _projection_text(_SNAPSHOT_STRONG)

        assert sentinel in text, (
            "changing the catalog did not change the output — the call site still "
            "holds a literal, so the strings were rewritten rather than migrated"
        )

    def test_the_keys_this_module_uses_exist_in_both_languages(self):
        for language in ("en", "es"):
            catalog = catalog_module._load_catalog.__wrapped__(language)
            keys = [k for k in catalog if k.startswith("report.impact_projection.")]
            assert len(keys) == 10, (
                f"expected 10 report.impact_projection.* keys in {language}, found {len(keys)}"
            )


# ── 6.8 / 6.9: the sweep that found what two earlier sweeps missed ────────────

_MIGRATED_MODULES = (
    "backend/services/impact_projection.py",
    "backend/services/pattern_discovery.py",
    "backend/services/researcher_topic_analytics.py",
    "backend/services/agentic_research_chat.py",
    "backend/services/assistant_actions.py",
    "backend/routers/dashboards.py",
)

#: Common Spanish function words. Two or more in one literal is the signal — a
#: single one appears in English strings often enough ("de facto", "la carte").
_SPANISH_WORDS = frozenset(
    """el la los las un una de del que con para por este esta sobre desde antes como
    mas muy son tiene tienen comparten conviene registros calidad lectura mapa expertos
    fuentes cobertura decisiones senal preliminar puente brecha fuerte variantes""".split()
)


def _spanish_literals(path):
    """Every string literal in a module that reads as Spanish.

    Walks the **AST**, not a regex over the source. Three sweeps of these files
    missed strings before this one, each for the same reason: they matched a
    shape someone had already seen. The inventory's extractor keyed on accents
    and lost three accent-free labels; the group A migration searched for
    `"label":` and `"recommended_action":` and lost three `"evidence":` fields;
    the first version of this check used a hand-written word alternation and
    lost the one string that happened not to contain any of its words.

    Reading every literal removes the guess. It can still misjudge a literal —
    but it cannot fail to look at one.
    """
    import ast

    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        elif isinstance(node, ast.JoinedStr):
            text = "".join(
                part.value
                for part in node.values
                if isinstance(part, ast.Constant) and isinstance(part.value, str)
            )
        else:
            continue
        if len(text) < 12:
            continue
        words = {w.strip(".,;:!?()'\"").lower() for w in text.split()}
        if len(words & _SPANISH_WORDS) >= 2:
            found.append((node.lineno, text[:90]))
    return sorted(set(found))


@pytest.mark.parametrize("module", _MIGRATED_MODULES)
def test_no_spanish_literal_survives_in_a_migrated_module(module):
    """Task 6.8. A regression gate, not a discovery tool.

    It cannot find Spanish in a module nobody listed here, and it judges by
    vocabulary rather than by meaning. What it does guarantee is that these six
    files do not quietly regain a Spanish literal.
    """
    survivors = _spanish_literals(module)

    assert not survivors, f"{module} still holds Spanish literals: {survivors}"
