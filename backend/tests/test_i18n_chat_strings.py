"""Chat replies come from the catalog, in the language the request resolved.

Phase 6 group B. Unlike the report surface, these strings are **Spanish-only
today** and answer a client that knows its language. Migrating them with a bare
`translate(key)` would hand every Spanish-speaking user English — the migration
would break half the readers rather than serve both. So the resolved language is
threaded from the request, and both directions are asserted here.
"""

from __future__ import annotations

import pytest

from backend import models
from backend.i18n import catalog as catalog_module
from backend.services.agentic_research_chat import (
    AgenticChatRequest,
    AgenticResearchChatService,
)

pytestmark = pytest.mark.reporting


def _ask(db_session, question: str, **overrides):
    user = db_session.query(models.User).filter(models.User.role == "super_admin").first()
    # Popped before the payload is built: `language` is a resolver argument, not
    # a request field, and AgenticChatRequest rejects unknown keys.
    language = overrides.pop("language", None)
    payload_kwargs = {
        "question": question,
        "mode": "auto",
        "domain_id": "science",
        "persist_trace": False,
        **overrides,
    }
    return AgenticResearchChatService.ask(
        db=db_session,
        payload=AgenticChatRequest(**payload_kwargs),
        current_user=user,
        org_id=None,
        language=language,
    )


def _unclear(monkeypatch):
    monkeypatch.setattr(
        AgenticResearchChatService,
        "_classify_intents",
        classmethod(lambda cls, question, integration: (set(), "llm")),
    )


class TestTheReplyFollowsTheRequestedLanguage:
    def test_spanish_is_still_served_in_spanish(self, monkeypatch, db_session):
        """The regression this threading exists to prevent.

        These strings are Spanish today. A migration that answered every reader
        in English would be a downgrade for the ones already served correctly.
        """
        _unclear(monkeypatch)

        answer = _ask(db_session, "asdf qwerty", language="es")["answer"]

        assert "No pude determinar" in answer

    def test_english_is_served_in_english(self, monkeypatch, db_session):
        """The defect: an English speaker was answered in Spanish."""
        _unclear(monkeypatch)

        answer = _ask(db_session, "asdf qwerty", language="en")["answer"]

        assert "could not tell" in answer.lower()
        assert "No pude determinar" not in answer

    def test_no_language_resolves_to_the_default(self, monkeypatch, db_session):
        _unclear(monkeypatch)

        assert _ask(db_session, "asdf qwerty")["answer"] == _ask(
            db_session, "asdf qwerty", language="en"
        )["answer"]


class TestFollowUpsFollowTheLanguage:
    @pytest.mark.parametrize(
        "language,marker", [("es", "Que evidencia"), ("en", "What evidence")]
    )
    def test_entity_follow_ups(self, monkeypatch, db_session, language, marker):
        _unclear(monkeypatch)

        follow_ups = _ask(db_session, "any question", entity_id=1, language=language)[
            "follow_up_questions"
        ]

        assert any(marker in q for q in follow_ups), f"{language}: got {follow_ups}"


class TestTheTextComesFromTheCatalog:
    """Distinguishes migration from translation-in-place — see group A."""

    def test_output_follows_the_catalog(self, monkeypatch, db_session):
        _unclear(monkeypatch)
        sentinel = "SENTINEL-CHAT"
        real_keys = [
            key
            for key in catalog_module._load_catalog.__wrapped__("en")
            if key.startswith("chat.")
        ]
        assert real_keys, "no chat.* keys in the catalog"
        monkeypatch.setattr(
            catalog_module, "_load_catalog", lambda language: {k: sentinel for k in real_keys}
        )

        answer = _ask(db_session, "asdf qwerty", language="en")["answer"]

        assert sentinel in answer, (
            "changing the catalog did not change the reply — the call site still "
            "holds a literal"
        )
