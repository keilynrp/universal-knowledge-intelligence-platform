from __future__ import annotations

from unittest.mock import patch

from backend import models
from backend.authority.base import AuthorityCandidate


_RESOLVE_PATCH = "backend.routers.authority._authority_resolve_all"


def _candidate(
    *,
    authority_source: str,
    authority_id: str,
    canonical_label: str,
    confidence: float,
    resolution_status: str = "exact_match",
    affiliation_score: float = 0.2,
) -> AuthorityCandidate:
    return AuthorityCandidate(
        authority_source=authority_source,
        authority_id=authority_id,
        canonical_label=canonical_label,
        aliases=[],
        description="Authority profile",
        confidence=confidence,
        uri=f"https://example.org/{authority_id}",
        score_breakdown={
            "identifiers": 1.0 if authority_source == "orcid" else 0.7,
            "name": confidence,
            "affiliation": affiliation_score,
            "coauthorship": 0.0,
            "topic": 0.0,
        },
        evidence=["us072_test_candidate"],
        resolution_status=resolution_status,
        merged_sources=[],
    )


def _payload(**overrides):
    payload = {
        "field_name": "author_name",
        "value": "Ada Lovelace",
        "context_affiliation": "Open Science Lab",
        "context_orcid_hint": "0000-0001-0000-0001",
    }
    payload.update(overrides)
    return payload


class TestAuthorAffiliationAuthorityLinks:
    _URL = "/authority/authors/resolve"

    def test_missing_affiliation_does_not_attempt_institution_resolution(self, client, editor_headers, db_session):
        with patch(_RESOLVE_PATCH, return_value=[
            _candidate(
                authority_source="orcid",
                authority_id="0000-0001-0000-0001",
                canonical_label="Ada Lovelace",
                confidence=0.97,
            )
        ]) as resolver:
            resp = client.post(
                self._URL,
                json=_payload(context_affiliation=None),
                headers=editor_headers,
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["affiliation_resolution"] == {
            "attempted": False,
            "reason": "missing_context_affiliation",
        }
        assert resolver.call_count == 1
        assert db_session.query(models.AuthorityRecord).count() == 1
        assert db_session.query(models.AuthorityRecordLink).count() == 0

    def test_author_resolve_persists_institution_and_pending_link(self, client, editor_headers, db_session):
        def resolve_side_effect(value, entity_type, context):
            if entity_type == "person":
                return [
                    _candidate(
                        authority_source="orcid",
                        authority_id="0000-0001-0000-0001",
                        canonical_label="Ada Lovelace",
                        confidence=0.97,
                    )
                ]
            if entity_type == "institution":
                return [
                    _candidate(
                        authority_source="openalex",
                        authority_id="I123",
                        canonical_label="Open Science Lab",
                        confidence=0.91,
                    )
                ]
            return []

        with patch(_RESOLVE_PATCH, side_effect=resolve_side_effect):
            resp = client.post(self._URL, json=_payload(), headers=editor_headers)

        assert resp.status_code == 201
        data = resp.json()
        affiliation = data["affiliation_resolution"]
        assert affiliation["attempted"] is True
        assert affiliation["records_created"] == 1
        assert affiliation["winning_record"]["authority_source"] == "openalex"
        assert affiliation["link"]["status"] == "pending"
        assert affiliation["link"]["link_type"] == "affiliated-with"

        records = db_session.query(models.AuthorityRecord).order_by(models.AuthorityRecord.id.asc()).all()
        assert [(row.field_name, row.authority_source) for row in records] == [
            ("author_name", "orcid"),
            ("affiliation", "openalex"),
        ]
        link = db_session.query(models.AuthorityRecordLink).one()
        assert link.source_authority_record_id == records[0].id
        assert link.target_authority_record_id == records[1].id
        assert link.status == "pending"
        assert link.confidence == 0.869

    def test_institution_nil_does_not_create_link(self, client, editor_headers, db_session):
        def resolve_side_effect(value, entity_type, context):
            if entity_type == "person":
                return [
                    _candidate(
                        authority_source="orcid",
                        authority_id="0000-0001-0000-0001",
                        canonical_label="Ada Lovelace",
                        confidence=0.97,
                    )
                ]
            return []

        with patch(_RESOLVE_PATCH, side_effect=resolve_side_effect):
            resp = client.post(self._URL, json=_payload(), headers=editor_headers)

        assert resp.status_code == 201
        affiliation = resp.json()["affiliation_resolution"]
        assert affiliation["attempted"] is True
        assert affiliation["winning_record"]["authority_source"] == "internal_nil"
        assert affiliation["link"] is None
        assert db_session.query(models.AuthorityRecord).count() == 2
        assert db_session.query(models.AuthorityRecordLink).count() == 0

    def test_confirm_and_reject_link_mutate_only_link(self, client, editor_headers, db_session):
        author = models.AuthorityRecord(
            field_name="author_name",
            original_value="Ada Lovelace",
            authority_source="orcid",
            authority_id="0000-0001-0000-0001",
            canonical_label="Ada Lovelace",
            aliases="[]",
            confidence=0.97,
            status="pending",
            resolution_status="exact_match",
            score_breakdown="{}",
            evidence="[]",
            merged_sources="[]",
            resolution_route="fast_path",
        )
        institution = models.AuthorityRecord(
            field_name="affiliation",
            original_value="Open Science Lab",
            authority_source="openalex",
            authority_id="I123",
            canonical_label="Open Science Lab",
            aliases="[]",
            confidence=0.91,
            status="pending",
            resolution_status="exact_match",
            score_breakdown="{}",
            evidence="[]",
            merged_sources="[]",
        )
        db_session.add_all([author, institution])
        db_session.flush()
        link = models.AuthorityRecordLink(
            source_authority_record_id=author.id,
            target_authority_record_id=institution.id,
            link_type="affiliated-with",
            confidence=0.87,
            status="pending",
            evidence="[]",
        )
        db_session.add(link)
        db_session.commit()

        confirm = client.post(f"/authority/links/{link.id}/confirm", headers=editor_headers)
        assert confirm.status_code == 200
        assert confirm.json()["status"] == "confirmed"
        db_session.refresh(author)
        db_session.refresh(institution)
        assert author.status == "pending"
        assert institution.status == "pending"

        reject = client.post(f"/authority/links/{link.id}/reject", headers=editor_headers)
        assert reject.status_code == 200
        assert reject.json()["status"] == "rejected"
        db_session.refresh(author)
        db_session.refresh(institution)
        assert author.status == "pending"
        assert institution.status == "pending"

    def test_affiliation_read_endpoint_returns_link_and_institution(self, client, editor_headers, db_session):
        author = models.AuthorityRecord(
            field_name="author_name",
            original_value="Ada Lovelace",
            authority_source="orcid",
            authority_id="0000-0001-0000-0001",
            canonical_label="Ada Lovelace",
            aliases="[]",
            confidence=0.97,
            status="pending",
            resolution_status="exact_match",
            score_breakdown="{}",
            evidence="[]",
            merged_sources="[]",
            resolution_route="fast_path",
        )
        institution = models.AuthorityRecord(
            field_name="affiliation",
            original_value="Open Science Lab",
            authority_source="openalex",
            authority_id="I123",
            canonical_label="Open Science Lab",
            aliases="[]",
            confidence=0.91,
            status="pending",
            resolution_status="exact_match",
            score_breakdown="{}",
            evidence="[]",
            merged_sources="[]",
        )
        db_session.add_all([author, institution])
        db_session.flush()
        link = models.AuthorityRecordLink(
            source_authority_record_id=author.id,
            target_authority_record_id=institution.id,
            link_type="affiliated-with",
            confidence=0.87,
            status="pending",
            evidence='["context_affiliation:Open Science Lab"]',
        )
        db_session.add(link)
        db_session.commit()

        resp = client.get(
            f"/authority/authors/review-queue/{author.id}/affiliations",
            headers=editor_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["author_record"]["id"] == author.id
        assert len(data["affiliations"]) == 1
        assert data["affiliations"][0]["link"]["id"] == link.id
        assert data["affiliations"][0]["institution_record"]["canonical_label"] == "Open Science Lab"
