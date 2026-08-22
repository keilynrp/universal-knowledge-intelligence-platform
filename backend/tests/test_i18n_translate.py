"""Catalog lookup — `translate(key, language, **params)`.

The catalog itself is the JSON projection committed by phase 2. These tests
exercise the lookup against a small injected catalog rather than the real one,
because the backend's own keys (`report.`, `email.`, `validation.`) do not
exist yet — they arrive with the string migration in phases 6 and 7. Testing
lookup against strings the change has not written would mean either waiting for
them or asserting on frontend keys the backend must never render.

One test does read the real projection, to prove the loader points at the file
phase 2 actually committed.
"""

import logging
from pathlib import Path

import pytest

from backend.i18n import DEFAULT_LANGUAGE, LANGUAGES
from backend.i18n import catalog as catalog_module
from backend.i18n.catalog import SURFACE_PREFIXES, translate

pytestmark = pytest.mark.reporting

_FIXTURE = {
    "en": {
        "report.section.hidden_patterns.title": "Hidden Patterns",
        "report.summary.count": "{count} entities in {domain}",
        "email.password_reset.subject": "{platform}: reset your password",
    },
    "es": {
        "report.section.hidden_patterns.title": "Patrones Ocultos",
        "report.summary.count": "{count} entidades en {domain}",
        "email.password_reset.subject": "{platform}: recupera tu contraseña",
    },
}


@pytest.fixture(autouse=True)
def _injected_catalog(monkeypatch):
    """Serve the fixture instead of the committed projection."""
    monkeypatch.setattr(
        catalog_module, "_load_catalog", lambda language: _FIXTURE.get(language, {})
    )
    yield


class TestLookup:
    def test_existing_key_in_english(self):
        assert translate("report.section.hidden_patterns.title", "en") == "Hidden Patterns"

    def test_same_key_in_spanish(self):
        assert translate("report.section.hidden_patterns.title", "es") == "Patrones Ocultos"

    def test_language_defaults_to_english(self):
        assert translate("report.section.hidden_patterns.title") == translate(
            "report.section.hidden_patterns.title", DEFAULT_LANGUAGE
        )


class TestMissingKeyDegrades:
    def test_absent_key_returns_the_key_and_does_not_raise(self):
        assert translate("report.nope.not_here", "en") == "report.nope.not_here"

    def test_absent_key_logs_a_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            translate("report.nope.not_here", "en")

        assert any(
            "report.nope.not_here" in record.getMessage() for record in caplog.records
        ), "the missing key must name itself in the log, or the warning is unactionable"

    def test_a_key_missing_only_in_spanish_falls_back_to_english(self, monkeypatch):
        """One-sided keys are a CI failure in phase 4, not a runtime crash here."""
        monkeypatch.setattr(
            catalog_module,
            "_load_catalog",
            lambda language: {"report.only_en": "English only"} if language == "en" else {},
        )

        assert translate("report.only_en", "es") == "English only"


class TestInterpolation:
    @pytest.mark.parametrize("language", LANGUAGES)
    def test_parameters_survive_in_both_languages(self, language):
        rendered = translate("report.summary.count", language, count=42, domain="science")

        assert "42" in rendered and "science" in rendered
        assert "{count}" not in rendered and "{domain}" not in rendered

    def test_interpolated_values_are_not_translated(self):
        """A value that happens to be a catalog key is still data, not copy."""
        rendered = translate(
            "report.summary.count",
            "es",
            count=1,
            domain="report.section.hidden_patterns.title",
        )

        assert "report.section.hidden_patterns.title" in rendered
        assert "Patrones Ocultos" not in rendered

    def test_a_missing_parameter_is_left_visible_rather_than_raising(self):
        """Mirrors the frontend, which replaces each param it is given.

        `str.format` would raise on the unsupplied placeholder and would also
        choke on any catalog string containing a literal brace. Rendering
        `{domain}` is a visible defect; failing report generation is an outage.
        """
        rendered = translate("report.summary.count", "en", count=7)

        assert "7" in rendered and "{domain}" in rendered


class TestKeyContract:
    @pytest.mark.parametrize("key", ["nav.home", "settings.title", "bare", ""])
    def test_a_key_without_a_surface_prefix_is_rejected(self, key):
        """The backend shares one key space with the frontend and owns part of it.

        Rendering `nav.home` into a PDF would put a sidebar label in a report.
        This is a call-site defect, deterministic and caught by any test that
        exercises the path — unlike a missing key, which is data and degrades.
        """
        with pytest.raises(ValueError) as excinfo:
            translate(key, "en")

        assert key in str(excinfo.value) or "prefix" in str(excinfo.value).lower()

    @pytest.mark.parametrize("prefix", SURFACE_PREFIXES)
    def test_every_declared_surface_prefix_is_accepted(self, prefix):
        translate(f"{prefix}whatever.unknown", "en")  # missing, but well-formed


class TestUnsupportedLanguage:
    """These assert on the resolver, not on the rendered string.

    Asserting only that `translate(..., "fr")` returns the English text does
    **not** test the fallback: with language resolution removed entirely, the
    lookup misses in the (empty) `fr` catalog and the missing-key path serves
    English anyway. The first version of these tests passed with the resolver
    deleted, so both were rewritten to name the mechanism they claim to cover.
    """

    def test_an_unsupported_language_resolves_to_the_default(self):
        assert catalog_module._resolve_language("fr") == DEFAULT_LANGUAGE

    def test_a_supported_language_resolves_to_itself(self):
        for language in LANGUAGES:
            assert catalog_module._resolve_language(language) == language

    def test_unknown_language_renders_in_the_default(self):
        assert translate("report.section.hidden_patterns.title", "fr") == "Hidden Patterns"

    def test_the_fallback_says_the_language_was_unsupported(self, caplog):
        """Distinct from the missing-key warning, which also names a language."""
        with caplog.at_level(logging.WARNING):
            translate("report.section.hidden_patterns.title", "fr")

        messages = [record.getMessage() for record in caplog.records]
        assert any("unsupported" in m and "fr" in m for m in messages), (
            f"no warning identified 'fr' as unsupported; got {messages}"
        )


class TestLoaderPointsAtTheCommittedProjection:
    def test_the_real_catalog_loads(self, monkeypatch):
        monkeypatch.undo()  # step past the injected fixture
        catalog_module._load_catalog.cache_clear()

        for language in LANGUAGES:
            assert len(catalog_module._load_catalog(language)) > 3000, (
                f"the {language} projection did not load from backend/i18n/"
            )


class TestLanguageCannotReachTheFilesystem:
    """CodeQL flagged `py/path-injection` here, and it was right to.

    `language` arrives from `?language=` and `Accept-Language`, and it was
    interpolated straight into a path. Nothing exploitable reached it — every
    caller goes through `_resolve_language` first — but that is a **non-local**
    invariant: it holds because of a function somewhere else, it is invisible to
    a reader of this one, and it is one direct call away from not holding.

    The guard therefore lives in `_load_catalog` itself, so the path cannot be
    derived from anything but a known language.
    """

    @pytest.mark.parametrize(
        "hostile",
        [
            "../../../../etc/passwd",
            "..\..\windows\win.ini",
            "en/../../secrets",
            "../catalog.en",
            "",
            ".",
        ],
    )
    def test_a_traversal_attempt_never_touches_the_filesystem(self, monkeypatch, hostile):
        """Asserting `== {}` would not discriminate.

        An unguarded loader also returns `{}` for these, because the path it
        builds happens not to exist — the `catalog.` prefix and `.json` suffix
        make the attack impractical rather than impossible. What separates a
        guard from luck is whether the path is consulted at all.
        """
        monkeypatch.undo()
        catalog_module._load_catalog.cache_clear()
        touched: list[str] = []
        real_exists = Path.exists
        monkeypatch.setattr(
            Path, "exists", lambda self: (touched.append(str(self)), real_exists(self))[1]
        )

        result = catalog_module._load_catalog(hostile)

        assert result == {}
        assert not touched, f"an unsupported language reached the filesystem: {touched}"

    def test_the_supported_languages_still_load(self, monkeypatch):
        monkeypatch.undo()
        catalog_module._load_catalog.cache_clear()

        for language in LANGUAGES:
            assert len(catalog_module._load_catalog(language)) > 3000

    def test_a_key_cannot_forge_a_log_line(self, caplog):
        """`py/log-injection`: a newline in a key must not fake a second record."""
        forged = "report.\nWARNING:root:transfer approved"

        with caplog.at_level(logging.WARNING):
            translate(forged, "en")

        for record in caplog.records:
            assert "\n" not in record.getMessage(), (
                f"a key forged a line break into the log: {record.getMessage()!r}"
            )
