"""Persisted localized messages (#269).

`enrichment_worker._set_enrichment_failed` and the demo portal seed used to
write already-rendered Spanish straight into the database: `evidence` and
`recommendations` inside `attributes_json["enrichment_failure"]`, and
`CatalogPortal.title`/`.description`. Whatever language happened to be active
at write time was frozen into the row, and a background worker has no
request to have a language from in the first place.

The fix is `backend/i18n/message_ref.py`: persist a key (+ params, for a
JSON-bearing field) instead of rendered text, and resolve only at the API
response boundary, once the request's language is known. This file tests
that boundary from both sides — what gets written, and what a reader gets
back — plus the specific promises the issue's contract makes: legacy rows
still work, a malformed ref cannot crash a response, and the worker itself
never chooses a language.
"""

from __future__ import annotations

import json

import pytest

from backend import models
from backend.enrichment_worker import (
    _set_enrichment_failed,
    resolve_enrichment_failure_for_response,
)
from backend.i18n.message_ref import (
    is_message_ref,
    looks_like_catalog_key,
    make_message_ref,
    resolve_message,
    resolve_message_list,
    resolve_plain_or_key,
)

pytestmark = pytest.mark.reporting


def _make_entity(db, name="Test Entity"):
    entity = models.RawEntity(primary_label=name, enrichment_status="processing")
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


# ── New writes store a reference, not rendered prose ──────────────────────────


def test_new_failure_stores_evidence_as_a_key_and_params_not_prose(db_session):
    entity = _make_entity(db_session)
    _set_enrichment_failed(
        entity,
        code="no_provider_match",
        evidence=make_message_ref(
            "validation.enrichment_failure.evidence.no_provider_match", query="Some Title"
        ),
    )

    failure = json.loads(entity.attributes_json)["enrichment_failure"]
    assert isinstance(failure["evidence"], dict), "evidence must be a structured ref, not a string"
    assert failure["evidence"]["type"] == "i18n_ref"
    assert failure["evidence"]["key"] == "validation.enrichment_failure.evidence.no_provider_match"
    assert failure["evidence"]["params"] == {"query": "Some Title"}
    # Never a rendered sentence in either language, in the stored form.
    assert "No matches were found" not in json.dumps(failure)
    assert "No se encontraron coincidencias" not in json.dumps(failure)


def test_new_failure_stores_recommendations_as_a_list_of_refs(db_session):
    entity = _make_entity(db_session)
    _set_enrichment_failed(
        entity, code="missing_title", evidence=make_message_ref("validation.enrichment_failure.evidence.missing_title")
    )

    failure = json.loads(entity.attributes_json)["enrichment_failure"]
    assert failure["recommendations"], "missing_title has recommendations"
    for rec in failure["recommendations"]:
        assert is_message_ref(rec)
        assert rec["key"].startswith("validation.enrichment_failure.recommendation.missing_title.")


@pytest.mark.parametrize(
    "code",
    ["missing_title", "no_provider_match", "data_error", "unexpected_error"],
)
def test_every_failure_code_recommendations_are_all_refs(db_session, code):
    """All four codes, not just one — a code added later inherits the same shape."""
    entity = _make_entity(db_session)
    _set_enrichment_failed(entity, code=code, evidence=make_message_ref(f"validation.enrichment_failure.evidence.{code}"))
    failure = json.loads(entity.attributes_json)["enrichment_failure"]
    assert failure["recommendations"]
    assert all(is_message_ref(r) for r in failure["recommendations"])


# ── The real write path (enrich_single_record) ────────────────────────────────


def test_enrich_single_record_missing_title_writes_a_ref(db_session):
    from backend.enrichment_worker import enrich_single_record

    entity = _make_entity(db_session, name=None)
    entity.primary_label = None
    db_session.commit()

    result = enrich_single_record(db_session, entity)
    failure = json.loads(result.attributes_json)["enrichment_failure"]
    assert is_message_ref(failure["evidence"])
    assert failure["evidence"]["key"] == "validation.enrichment_failure.evidence.missing_title"


# ── The same stored value resolves correctly in EN and ES ─────────────────────


def test_same_stored_evidence_resolves_in_both_languages(db_session):
    entity = _make_entity(db_session)
    _set_enrichment_failed(
        entity,
        code="no_provider_match",
        evidence=make_message_ref(
            "validation.enrichment_failure.evidence.no_provider_match", query="Graph Learning"
        ),
    )
    stored = entity.attributes_json

    en = json.loads(resolve_enrichment_failure_for_response(stored, "en"))
    es = json.loads(resolve_enrichment_failure_for_response(stored, "es"))

    en_evidence = en["enrichment_failure"]["evidence"]
    es_evidence = es["enrichment_failure"]["evidence"]
    assert isinstance(en_evidence, str) and isinstance(es_evidence, str)
    assert en_evidence != es_evidence
    assert "Graph Learning" in en_evidence and "Graph Learning" in es_evidence
    assert "No matches were found" in en_evidence
    assert "No se encontraron coincidencias" in es_evidence
    # The original stored string is untouched — resolution is read-only.
    assert json.loads(stored)["enrichment_failure"]["evidence"] == {
        "type": "i18n_ref",
        "key": "validation.enrichment_failure.evidence.no_provider_match",
        "params": {"query": "Graph Learning"},
    }


def test_same_stored_recommendations_resolve_in_both_languages(db_session):
    entity = _make_entity(db_session)
    _set_enrichment_failed(
        entity, code="data_error", evidence=make_message_ref("validation.enrichment_failure.evidence.data_error", error="boom")
    )
    stored = entity.attributes_json

    en = json.loads(resolve_enrichment_failure_for_response(stored, "en"))["enrichment_failure"]["recommendations"]
    es = json.loads(resolve_enrichment_failure_for_response(stored, "es"))["enrichment_failure"]["recommendations"]

    assert all(isinstance(r, str) for r in en)
    assert all(isinstance(r, str) for r in es)
    assert en != es
    assert any("DOI" in r for r in en)
    assert any("DOI" in r for r in es)


# ── Legacy rendered strings remain unchanged ───────────────────────────────────


def _legacy_failure_json() -> str:
    return json.dumps(
        {
            "enrichment_failure": {
                "code": "no_provider_match",
                "evidence": "No se encontraron coincidencias para 'Old Title' en las fuentes de enriquecimiento disponibles.",
                "recommendations": [
                    "Revise que el título no tenga abreviaturas, HTML residual o errores tipográficos.",
                    "Agregue o corrija el DOI para aumentar la probabilidad de coincidencia.",
                ],
                "provider_attempts": ["openalex"],
            }
        },
        ensure_ascii=False,
    )


@pytest.mark.parametrize("language", ["en", "es"])
def test_legacy_rendered_evidence_is_unchanged_regardless_of_requested_language(language):
    legacy = _legacy_failure_json()
    resolved = resolve_enrichment_failure_for_response(legacy, language)
    assert resolved == legacy, "a legacy row must round-trip byte-for-byte, in every language"


def test_legacy_row_evidence_is_not_mistaken_for_a_ref():
    legacy_evidence = json.loads(_legacy_failure_json())["enrichment_failure"]["evidence"]
    assert not is_message_ref(legacy_evidence)
    assert resolve_message(legacy_evidence, "es") == legacy_evidence


def test_legacy_row_recommendations_pass_through_unchanged():
    legacy_recs = json.loads(_legacy_failure_json())["enrichment_failure"]["recommendations"]
    assert resolve_message_list(legacy_recs, "en") == legacy_recs


def test_a_row_with_no_enrichment_failure_is_untouched():
    raw = json.dumps({"enrichment_authors": ["Alice"]})
    assert resolve_enrichment_failure_for_response(raw, "es") == raw


@pytest.mark.parametrize("raw", [None, "", "{}", "not json at all"])
def test_absent_or_malformed_attributes_json_is_returned_as_is(raw):
    assert resolve_enrichment_failure_for_response(raw, "en") == raw


# ── Malformed refs fail safely ─────────────────────────────────────────────────


class TestMalformedRefsFailSafely:
    """None of these may raise. Each is a plausible corruption: a ref missing
    a field, one whose key lost its surface prefix, or a dict that merely
    resembles a ref by accident."""

    def test_missing_key_field_is_not_even_recognised_as_a_ref(self):
        """No `key` at all means it fails the shape check outright, not the
        malformed-ref check inside resolve_message — so it passes through
        unchanged, same as any other dict this module does not own."""
        value = {"type": "i18n_ref", "params": {}}
        assert not is_message_ref(value)
        assert resolve_message(value, "en") == value

    def test_key_without_a_surface_prefix(self):
        # is_message_ref() is shape-only; the prefix check is resolve_message's job.
        bad = {"type": "i18n_ref", "key": "not.a.real.prefix", "params": {}}
        assert resolve_message(bad, "en") == ""

    def test_params_is_not_a_mapping(self):
        bad = {"type": "i18n_ref", "key": "validation.enrichment_failure.evidence.missing_title", "params": "oops"}
        assert resolve_message(bad, "en") == ""

    def test_key_not_a_string(self):
        bad = {"type": "i18n_ref", "key": 42, "params": {}}
        assert not is_message_ref(bad)
        assert resolve_message(bad, "en") == bad  # not a ref at all — passed through

    def test_a_foreign_dict_sharing_the_key_field_name_is_not_a_ref(self):
        """The type marker exists precisely so this does not get resolved."""
        foreign = {"key": "validation.enrichment_failure.evidence.missing_title", "note": "unrelated data"}
        assert not is_message_ref(foreign)
        assert resolve_message(foreign, "en") == foreign

    def test_resolve_message_list_on_a_mixed_and_malformed_list(self):
        values = [
            "a legacy sentence",
            make_message_ref("validation.enrichment_failure.recommendation.missing_title.0"),
            {"type": "i18n_ref", "key": "nonsense"},  # malformed: no surface prefix
            None,
        ]
        resolved = resolve_message_list(values, "en")
        assert resolved[0] == "a legacy sentence"
        assert isinstance(resolved[1], str) and resolved[1]
        assert resolved[2] == ""
        assert resolved[3] is None

    def test_none_and_scalars_pass_through(self):
        assert resolve_message(None, "en") is None
        assert resolve_message(42, "en") == 42
        assert resolve_message_list(None, "en") is None
        assert resolve_message_list("not a list", "en") == "not a list"


# ── The worker persists no locale ──────────────────────────────────────────────


def test_stored_failure_carries_no_language_or_locale_field(db_session):
    entity = _make_entity(db_session)
    _set_enrichment_failed(
        entity,
        code="unexpected_error",
        evidence=make_message_ref(
            "validation.enrichment_failure.evidence.unexpected_error",
            error_type="RuntimeError",
            error="boom",
        ),
    )
    blob = entity.attributes_json.lower()
    assert '"language"' not in blob
    assert '"locale"' not in blob
    assert '"lang"' not in blob


def test_make_message_ref_signature_has_no_language_parameter():
    import inspect

    assert "language" not in inspect.signature(make_message_ref).parameters
    assert "locale" not in inspect.signature(make_message_ref).parameters


def test_the_same_ref_is_written_however_the_response_will_later_be_read():
    """The write path cannot see the future reader's language because it
    never asks for one — this is the structural half of "the worker persists
    no locale", not just an absence-of-a-field check."""
    ref_a = make_message_ref("validation.enrichment_failure.evidence.missing_title")
    ref_b = make_message_ref("validation.enrichment_failure.evidence.missing_title")
    assert ref_a == ref_b


# ── Demo portal: legacy and new persistence paths both work ───────────────────


def test_new_demo_portal_title_is_a_catalog_key_not_rendered_text():
    from backend.routers.demo import _DEMO_PORTAL_DESCRIPTION, _DEMO_PORTAL_TITLE

    assert looks_like_catalog_key(_DEMO_PORTAL_TITLE)
    assert looks_like_catalog_key(_DEMO_PORTAL_DESCRIPTION)
    assert _DEMO_PORTAL_TITLE == "dashboard.demo_portal.title"
    assert _DEMO_PORTAL_DESCRIPTION == "dashboard.demo_portal.description"


@pytest.mark.parametrize("language,expected_title", [("en", "UKIP Demo Portal"), ("es", "Portal demo UKIP")])
def test_new_demo_portal_key_resolves_per_language(language, expected_title):
    from backend.routers.demo import _DEMO_PORTAL_TITLE

    assert resolve_plain_or_key(_DEMO_PORTAL_TITLE, language) == expected_title


def test_legacy_demo_portal_literal_title_is_unchanged_in_every_language():
    legacy_title = "Portal demo UKIP"  # what a pre-#269 row holds verbatim
    assert not looks_like_catalog_key(legacy_title)
    assert resolve_plain_or_key(legacy_title, "en") == legacy_title
    assert resolve_plain_or_key(legacy_title, "es") == legacy_title


def test_legacy_portal_description_is_none_safe():
    assert resolve_plain_or_key(None, "en") is None


# ── API-level: the read boundary resolves what the worker wrote ───────────────


def test_entity_endpoint_resolves_evidence_into_the_requested_language(client, auth_headers, db_session):
    entity = models.RawEntity(primary_label=None, enrichment_status="processing")
    db_session.add(entity)
    db_session.commit()
    db_session.refresh(entity)

    resp = client.post(f"/enrich/row/{entity.id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text[:300]

    en = client.get(f"/entities/{entity.id}?language=en", headers=auth_headers)
    es = client.get(f"/entities/{entity.id}?language=es", headers=auth_headers)
    assert en.status_code == 200 and es.status_code == 200

    en_failure = json.loads(en.json()["attributes_json"])["enrichment_failure"]
    es_failure = json.loads(es.json()["attributes_json"])["enrichment_failure"]

    assert isinstance(en_failure["evidence"], str)
    assert isinstance(es_failure["evidence"], str)
    assert en_failure["evidence"] != es_failure["evidence"]
    assert "no title or primary label" in en_failure["evidence"]
    assert "título o etiqueta principal" in es_failure["evidence"]
    # Never a raw, unresolved key reaching the client.
    assert "validation." not in en.text
    assert "validation." not in es.text


def test_entity_endpoint_omitting_language_defaults_to_english(client, auth_headers, db_session):
    entity = models.RawEntity(primary_label=None, enrichment_status="processing")
    db_session.add(entity)
    db_session.commit()
    db_session.refresh(entity)
    client.post(f"/enrich/row/{entity.id}", headers=auth_headers)

    resp = client.get(f"/entities/{entity.id}", headers=auth_headers)
    failure = json.loads(resp.json()["attributes_json"])["enrichment_failure"]
    assert "no title or primary label" in failure["evidence"]


def test_entities_list_endpoint_also_resolves_failures(client, auth_headers, db_session):
    entity = models.RawEntity(primary_label=None, enrichment_status="processing")
    db_session.add(entity)
    db_session.commit()
    db_session.refresh(entity)
    client.post(f"/enrich/row/{entity.id}", headers=auth_headers)

    resp = client.get("/entities?language=es&limit=500", headers=auth_headers)
    assert resp.status_code == 200
    rows = {row["id"]: row for row in resp.json()}
    failure = json.loads(rows[entity.id]["attributes_json"])["enrichment_failure"]
    assert "título o etiqueta principal" in failure["evidence"]
