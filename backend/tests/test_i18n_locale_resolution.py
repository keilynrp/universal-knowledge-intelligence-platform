"""Per-request locale resolution.

Two resolvers, deliberately not one. The general API resolves in the order
explicit parameter → `Accept-Language` → default. **Report generation skips the
header entirely**: a report is produced for an audience, not for whoever pressed
the button, so an operator's browser locale must not leak into someone else's
artefact. That was settled with the product owner on 2026-07-31 and is written
into `backend-locale-resolution`.

Nothing calls these yet. Report generation gains its parameter in phase 8; email
in phase 7.
"""

import logging

import pytest

from backend.i18n import DEFAULT_LANGUAGE
from backend.i18n import locale as locale_module
from backend.i18n.locale import resolve_language, resolve_report_language

pytestmark = pytest.mark.reporting


class TestPrecedenceChain:
    def test_explicit_parameter_beats_the_header(self):
        assert resolve_language(explicit="es", accept_language="en-US,en;q=0.9") == "es"
        assert resolve_language(explicit="en", accept_language="es-MX,es;q=0.9") == "en"

    def test_header_is_used_when_no_parameter_is_given(self):
        assert resolve_language(explicit=None, accept_language="es-MX,es;q=0.9") == "es"

    def test_default_is_used_when_neither_is_present(self):
        assert resolve_language(explicit=None, accept_language=None) == DEFAULT_LANGUAGE
        assert resolve_language(explicit=None, accept_language="") == DEFAULT_LANGUAGE

    def test_the_default_is_english(self):
        assert DEFAULT_LANGUAGE == "en"


class TestAcceptLanguageParsing:
    @pytest.mark.parametrize(
        "header,expected",
        [
            ("es", "es"),
            ("es-MX", "es"),
            ("ES-mx", "es"),
            ("en-GB,en;q=0.8", "en"),
            # q-values order the candidates, not their position in the string.
            ("en;q=0.2,es;q=0.9", "es"),
            ("es;q=0.3,en;q=0.7", "en"),
            # A missing q defaults to 1.0 and therefore outranks any explicit q.
            ("es,en;q=0.9", "es"),
            # Unsupported languages are skipped, not treated as a failure.
            ("fr,de;q=0.9,es;q=0.5", "es"),
            # q=0 means "not acceptable" (RFC 9110) and must never be selected.
            # `es;q=0` alone is the case that discriminates: if q=0 entries were
            # merely ranked last instead of dropped, Spanish would still be the
            # only candidate and would win. Pairing it with a higher-q entry
            # proves nothing, because the ordering alone already decides that.
            ("es;q=0", "en"),
            ("es;q=0,en;q=0.4", "en"),
            ("es;q=0,en;q=0", "en"),
            # A malformed q does not discard an unambiguous tag. The client said
            # Spanish; only the priority is unreadable, and refusing the whole
            # entry would make the reader pay for the client's mistake.
            ("es;q=abc", "es"),
        ],
    )
    def test_header_variants(self, header, expected):
        assert resolve_language(explicit=None, accept_language=header) == expected

    @pytest.mark.parametrize("header", ["fr", "de,ja;q=0.8", "*", "   ", ";;;"])
    def test_headers_with_nothing_usable_fall_back_to_the_default(self, header):
        assert resolve_language(explicit=None, accept_language=header) == DEFAULT_LANGUAGE

    def test_a_malformed_header_does_not_raise(self):
        """A header is attacker-controllable input; it must never 500."""
        for header in ["q=", "en;;q=", "\x00", "a" * 5000, "es;q=1;q=2"]:
            assert resolve_language(explicit=None, accept_language=header) in ("en", "es")


class TestUnsupportedLanguage:
    def test_an_unsupported_explicit_parameter_falls_back_rather_than_failing(self):
        assert resolve_language(explicit="fr", accept_language=None) == DEFAULT_LANGUAGE

    def test_the_fallback_is_logged(self, caplog):
        with caplog.at_level(logging.WARNING):
            resolve_language(explicit="fr", accept_language=None)

        messages = [r.getMessage() for r in caplog.records]
        assert any("fr" in m and "unsupported" in m for m in messages), (
            f"an unsupported request must be observable rather than silent; got {messages}"
        )

    def test_an_unsupported_parameter_does_not_silently_defer_to_the_header(self):
        """`?language=fr` with a Spanish browser is still English.

        Falling through to the header would answer a question the caller did
        not ask: they named a language, and it is not available. Honouring the
        browser instead would hide that behind a plausible-looking result.
        """
        assert resolve_language(explicit="fr", accept_language="es") == DEFAULT_LANGUAGE


class TestReportGenerationIgnoresTheHeader:
    def test_an_explicit_report_language_is_honoured(self):
        assert resolve_report_language(explicit="es") == "es"

    def test_a_report_with_no_parameter_is_english_whatever_the_browser_says(self):
        """The decision this whole resolver split exists for."""
        assert resolve_report_language(explicit=None) == DEFAULT_LANGUAGE

    def test_report_resolution_takes_no_header_at_all(self):
        """Not "ignores it" by convention — it cannot receive one.

        A resolver that accepted the header and chose not to read it would be
        one refactor away from reading it. Asserting on the signature makes the
        boundary structural.
        """
        import inspect

        parameters = inspect.signature(resolve_report_language).parameters
        assert "accept_language" not in parameters, (
            "report language resolution must not be able to see Accept-Language"
        )
        assert set(parameters) == {"explicit"}


class TestFastAPIDependency:
    def test_the_dependency_reads_the_query_parameter_and_the_header(self):
        assert locale_module.language_dependency(language="es", accept_language=None) == "es"
        assert locale_module.language_dependency(language=None, accept_language="es") == "es"
        assert locale_module.language_dependency(language=None, accept_language=None) == "en"

    def test_the_dependency_is_wired_for_fastapi(self):
        """Defaults must be FastAPI markers, or the route gains stray arguments."""
        import inspect

        from fastapi import params

        parameters = inspect.signature(locale_module.language_dependency).parameters
        assert isinstance(parameters["language"].default, params.Query)
        assert isinstance(parameters["accept_language"].default, params.Header)
