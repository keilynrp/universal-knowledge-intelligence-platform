"""Tests for institution_authority.py — Task 3.2."""
import pytest

from backend.services.institution_authority import (
    InstitutionAuthority,
    InstitutionAuthorityStore,
)


class TestCreateOrReuse:
    def test_create_new(self):
        store = InstitutionAuthorityStore()
        record, is_new = store.create_or_reuse("MIT", ror_id="ror-mit")
        assert is_new is True
        assert record.id == 1
        assert record.canonical_name == "MIT"
        assert record.ror_id == "ror-mit"
        assert record.status == "pending"
        assert record.created_at != ""

    def test_reuse_by_ror(self):
        store = InstitutionAuthorityStore()
        r1, new1 = store.create_or_reuse("MIT", ror_id="ror-mit")
        r2, new2 = store.create_or_reuse("Massachusetts Institute of Technology", ror_id="ror-mit")
        assert new1 is True
        assert new2 is False
        assert r1.id == r2.id

    def test_reuse_by_openalex(self):
        store = InstitutionAuthorityStore()
        r1, _ = store.create_or_reuse("Harvard", openalex_id="I123")
        r2, new2 = store.create_or_reuse("Harvard University", openalex_id="I123")
        assert new2 is False
        assert r1.id == r2.id

    def test_ror_case_insensitive(self):
        store = InstitutionAuthorityStore()
        store.create_or_reuse("MIT", ror_id="ROR-MIT")
        _, is_new = store.create_or_reuse("MIT", ror_id="ror-mit")
        assert is_new is False

    def test_no_identifiers_always_new(self):
        store = InstitutionAuthorityStore()
        _, new1 = store.create_or_reuse("Lab A")
        _, new2 = store.create_or_reuse("Lab A")
        assert new1 is True
        assert new2 is True

    def test_aliases_and_metadata(self):
        store = InstitutionAuthorityStore()
        r, _ = store.create_or_reuse(
            "ETH Zurich",
            ror_id="ror-eth",
            aliases=["ETHZ", "Swiss Federal Institute"],
            country_code="CH",
            institution_type="education",
            confidence=0.95,
            source_identifiers=["src-1"],
        )
        assert r.aliases == ["ETHZ", "Swiss Federal Institute"]
        assert r.country_code == "CH"
        assert r.institution_type == "education"
        assert r.confidence == 0.95
        assert r.source_identifiers == ["src-1"]

    def test_sequential_ids(self):
        store = InstitutionAuthorityStore()
        r1, _ = store.create_or_reuse("A")
        r2, _ = store.create_or_reuse("B")
        assert r1.id == 1
        assert r2.id == 2


class TestAcceptReject:
    def test_accept(self):
        store = InstitutionAuthorityStore()
        store.create_or_reuse("MIT", ror_id="ror-mit")
        result = store.accept(1)
        assert result is not None
        assert result.status == "confirmed"
        assert result.confirmed_at is not None

    def test_accept_missing(self):
        store = InstitutionAuthorityStore()
        assert store.accept(999) is None

    def test_reject(self):
        store = InstitutionAuthorityStore()
        store.create_or_reuse("MIT", ror_id="ror-mit")
        result = store.reject(1)
        assert result is not None
        assert result.status == "rejected"

    def test_reject_missing(self):
        store = InstitutionAuthorityStore()
        assert store.reject(999) is None


class TestFinders:
    def test_find_by_ror(self):
        store = InstitutionAuthorityStore()
        store.create_or_reuse("MIT", ror_id="ror-mit")
        found = store.find_by_ror("ror-mit")
        assert found is not None
        assert found.canonical_name == "MIT"

    def test_find_by_ror_not_found(self):
        store = InstitutionAuthorityStore()
        assert store.find_by_ror("nope") is None

    def test_find_by_openalex(self):
        store = InstitutionAuthorityStore()
        store.create_or_reuse("Harvard", openalex_id="I999")
        found = store.find_by_openalex("I999")
        assert found is not None

    def test_find_by_openalex_not_found(self):
        store = InstitutionAuthorityStore()
        assert store.find_by_openalex("nope") is None


class TestListAndGet:
    def test_list_all(self):
        store = InstitutionAuthorityStore()
        store.create_or_reuse("A")
        store.create_or_reuse("B")
        assert len(store.list_records()) == 2

    def test_list_by_status(self):
        store = InstitutionAuthorityStore()
        store.create_or_reuse("A")
        store.create_or_reuse("B")
        store.accept(1)
        assert len(store.list_records("confirmed")) == 1
        assert len(store.list_records("pending")) == 1

    def test_get(self):
        store = InstitutionAuthorityStore()
        store.create_or_reuse("A")
        assert store.get(1) is not None
        assert store.get(999) is None

    def test_to_dict(self):
        store = InstitutionAuthorityStore()
        store.create_or_reuse("MIT", ror_id="ror-mit")
        d = store.get(1).to_dict()
        assert d["canonical_name"] == "MIT"
        assert d["status"] == "pending"
