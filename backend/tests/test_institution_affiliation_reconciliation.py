from __future__ import annotations

import json
from unittest.mock import patch

from backend import models
from backend.services.institution_reconciliation import (
    InstitutionCandidate,
    RORRecord,
    extract_institution_candidates,
    normalize_institution_name,
    parse_ror_record,
    score_institution_match,
)


def _ror_record(**overrides) -> RORRecord:
    data = {
        "ror_id": "03yrm5c26",
        "name": "Open Science Lab",
        "aliases": ["Open Science Laboratory"],
        "acronyms": ["OSL"],
        "country_code": "US",
        "types": ["Facility"],
        "external_ids": {"openalex": {"all": ["I123"]}},
    }
    data.update(overrides)
    return RORRecord(**data)


def _entity(db_session, attributes: dict) -> models.RawEntity:
    entity = models.RawEntity(
        primary_label="Scientific record",
        domain="science",
        entity_type="publication",
        attributes_json=json.dumps(attributes),
    )
    db_session.add(entity)
    db_session.commit()
    db_session.refresh(entity)
    return entity


def test_normalize_institution_name_strips_generic_terms_and_punctuation():
    assert normalize_institution_name("The University of Open-Science, Institute") == "open science"


def test_parse_ror_record_supports_names_aliases_and_external_ids():
    record = parse_ror_record({
        "id": "https://ror.org/03yrm5c26",
        "names": [
            {"value": "Open Science Lab", "types": ["ror_display"]},
            {"value": "Open Science Laboratory", "types": ["alias"]},
            {"value": "OSL", "types": ["acronym"]},
        ],
        "country": {"country_code": "US", "country_name": "United States"},
        "types": ["Facility"],
        "links": [{"value": "https://open-science.example"}],
        "external_ids": {"openalex": {"all": ["I123"]}},
    })

    assert record.ror_id == "03yrm5c26"
    assert record.name == "Open Science Lab"
    assert record.aliases == ["Open Science Laboratory"]
    assert record.acronyms == ["OSL"]
    assert record.country_code == "US"
    assert record.external_ids["openalex"]["all"] == ["I123"]


def test_extract_institution_candidates_prefers_structured_and_dedupes():
    candidates = extract_institution_candidates({
        "canonical_affiliations": [
            {
                "name": "Open Science Lab",
                "ror": "https://ror.org/03yrm5c26",
                "openalex_id": "I123",
                "country_code": "US",
                "type": "institution",
            },
            {
                "name": "Open Science Laboratory",
                "ror": "03yrm5c26",
                "country_code": "US",
            },
        ],
        "author_affiliations": [
            {
                "author_name": "Ada Lovelace",
                "institutions": [{"name": "Other Lab", "country_code": "GB"}],
            }
        ],
    })

    assert [candidate.name for candidate in candidates] == ["Open Science Lab", "Other Lab"]
    assert candidates[0].ror == "03yrm5c26"


def test_extract_institution_candidates_falls_back_to_legacy_text():
    candidates = extract_institution_candidates({"affiliations": "Open Science Lab, US; Other Lab, GB"})
    assert [candidate.name for candidate in candidates] == ["Open Science Lab", "Other Lab"]
    assert all(candidate.source_field == "legacy_affiliations" for candidate in candidates)


def test_score_institution_match_uses_ror_openalex_alias_and_country_penalty():
    exact = score_institution_match(
        InstitutionCandidate(name="Wrong label", ror="https://ror.org/03yrm5c26"),
        _ror_record(),
    )
    assert exact.score == 0.98
    assert "exact_ror_match" in exact.evidence

    openalex = score_institution_match(
        InstitutionCandidate(name="Wrong label", openalex_id="I123"),
        _ror_record(),
    )
    assert openalex.score == 0.94
    assert "openalex_id_match" in openalex.evidence

    alias = score_institution_match(
        InstitutionCandidate(name="Open Science Laboratory", country_code="US"),
        _ror_record(),
    )
    assert alias.score >= 0.9
    assert "alias_or_acronym_match" in alias.evidence

    mismatch = score_institution_match(
        InstitutionCandidate(name="Open Science Lab", country_code="GB"),
        _ror_record(),
    )
    assert mismatch.score < alias.score
    assert "country_mismatch" in mismatch.evidence


def test_preview_and_apply_institution_reconciliation(client, editor_headers, db_session):
    entity = _entity(db_session, {
        "canonical_affiliations": [
            {
                "name": "Open Science Lab",
                "ror": "https://ror.org/03yrm5c26",
                "openalex_id": "I123",
                "country_code": "US",
            }
        ]
    })

    with patch("backend.routers.authority.RORAdapter.lookup", return_value=_ror_record()):
        preview = client.post(
            "/authority/institutions/reconcile/preview",
            json={"entity_ids": [entity.id]},
            headers=editor_headers,
        )
        applied = client.post(
            "/authority/institutions/reconcile/apply",
            json={"entity_ids": [entity.id]},
            headers=editor_headers,
        )
        reused = client.post(
            "/authority/institutions/reconcile/apply",
            json={"entity_ids": [entity.id]},
            headers=editor_headers,
        )

    assert preview.status_code == 200
    assert preview.json()["items"][0]["best_match"]["status"] == "exact_match"
    assert applied.status_code == 200
    assert applied.json()["created"] == 1
    assert applied.json()["records"][0]["status"] == "confirmed"
    assert applied.json()["records"][0]["authority_source"] == "ror"
    assert reused.json()["reused"] == 1
    assert db_session.query(models.AuthorityRecord).count() == 1


def test_institution_review_queue_accept_and_reject(client, editor_headers, db_session):
    pending = models.AuthorityRecord(
        field_name="affiliation",
        original_value="Ambiguous Lab",
        authority_source="ror",
        authority_id="01abcde99",
        canonical_label="Ambiguous Lab",
        confidence=0.76,
        status="pending",
        resolution_status="probable_match",
        score_breakdown="{}",
        evidence="[]",
        merged_sources='["ror:01abcde99"]',
        review_required=True,
    )
    rejected = models.AuthorityRecord(
        field_name="affiliation",
        original_value="Another Lab",
        authority_source="ror",
        authority_id="02abcde99",
        canonical_label="Another Lab",
        confidence=0.72,
        status="pending",
        resolution_status="probable_match",
        score_breakdown="{}",
        evidence="[]",
        merged_sources='["ror:02abcde99"]',
        review_required=True,
    )
    db_session.add_all([pending, rejected])
    db_session.commit()

    queue = client.get("/authority/institutions/review-queue", headers=editor_headers)
    accept = client.post(f"/authority/institutions/review-queue/{pending.id}/accept", headers=editor_headers)
    reject = client.post(f"/authority/institutions/review-queue/{rejected.id}/reject", headers=editor_headers)

    assert queue.status_code == 200
    assert queue.json()["total"] == 2
    assert accept.json()["status"] == "confirmed"
    assert accept.json()["review_required"] is False
    assert reject.json()["status"] == "rejected"
    assert reject.json()["review_required"] is False


def test_viewer_cannot_preview_or_apply_institution_reconciliation(client, viewer_headers):
    payload = {"entity_ids": [], "limit": 1}
    preview = client.post("/authority/institutions/reconcile/preview", json=payload, headers=viewer_headers)
    apply = client.post("/authority/institutions/reconcile/apply", json=payload, headers=viewer_headers)
    assert preview.status_code == 403
    assert apply.status_code == 403
