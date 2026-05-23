"""
Sprint 74 — LLM-Assisted Column Mapping tests.

Covers:
- POST /upload/suggest-mapping: auth guard, no-integration response, valid mapping
- _parse_llm_mapping: clean JSON, markdown-fenced JSON, partial JSON, bad JSON, unknown fields
- suggest_column_mapping graceful degradation when adapter.chat raises
- Column not in LLM response is filled with null
- Only unmapped columns overwritten (frontend logic, tested via endpoint response shape)
"""
import json
import pytest
from unittest.mock import MagicMock, patch


# ── _parse_llm_mapping unit tests ─────────────────────────────────────────────

from backend.routers.column_maps import COLUMN_MAPPING, COMMERCE_COLUMN_MAPPING, CORE_COLUMN_MAPPING
from backend.routers.ingest import _parse_llm_mapping, _VALID_UKIP_FIELDS


class TestParseLlmMapping:
    def test_clean_json(self):
        raw = '{"Title": "primary_label", "Author": "secondary_label"}'
        result = _parse_llm_mapping(raw, _VALID_UKIP_FIELDS)
        assert result["Title"] == "primary_label"
        assert result["Author"] == "secondary_label"

    def test_markdown_fenced(self):
        raw = "```json\n{\"DOI\": \"enrichment_doi\"}\n```"
        result = _parse_llm_mapping(raw, _VALID_UKIP_FIELDS)
        assert result["DOI"] == "enrichment_doi"

    def test_json_with_preamble(self):
        raw = 'Here is the mapping:\n{"DOI": "canonical_id", "Foo": null}'
        result = _parse_llm_mapping(raw, _VALID_UKIP_FIELDS)
        assert result["DOI"] == "canonical_id"
        assert result["Foo"] is None

    def test_null_value_preserved(self):
        raw = '{"UnknownCol": null}'
        result = _parse_llm_mapping(raw, _VALID_UKIP_FIELDS)
        assert result["UnknownCol"] is None

    def test_empty_string_value_coerced_to_none(self):
        raw = '{"EmptyCol": ""}'
        result = _parse_llm_mapping(raw, _VALID_UKIP_FIELDS)
        assert result["EmptyCol"] is None

    def test_unknown_field_coerced_to_none(self):
        raw = '{"Col": "nonexistent_field_xyz"}'
        result = _parse_llm_mapping(raw, _VALID_UKIP_FIELDS)
        assert result["Col"] is None

    def test_completely_invalid_json_returns_empty(self):
        raw = "Sorry, I cannot help with this request."
        result = _parse_llm_mapping(raw, _VALID_UKIP_FIELDS)
        assert result == {}

    def test_all_valid_fields_accepted(self):
        mapping_json = {col: col for col in _VALID_UKIP_FIELDS}
        raw = json.dumps(mapping_json)
        result = _parse_llm_mapping(raw, _VALID_UKIP_FIELDS)
        for field in _VALID_UKIP_FIELDS:
            assert result[field] == field


# ── POST /upload/suggest-mapping integration tests ────────────────────────────

class TestSuggestMappingEndpoint:
    def test_requires_auth(self, client):
        resp = client.post(
            "/upload/suggest-mapping",
            json={"columns": ["Title", "Author"], "sample_rows": []},
        )
        assert resp.status_code in (401, 403)

    def test_viewer_cannot_suggest(self, client, viewer_headers):
        resp = client.post(
            "/upload/suggest-mapping",
            json={"columns": ["Title"], "sample_rows": []},
            headers=viewer_headers,
        )
        assert resp.status_code in (401, 403)

    def test_no_integration_returns_200_not_available(self, client, editor_headers, db_session):
        # Ensure no active integration exists
        from backend import models
        db_session.query(models.AIIntegration).update({"is_active": False})
        db_session.commit()

        resp = client.post(
            "/upload/suggest-mapping",
            json={"columns": ["Title", "Author"], "sample_rows": []},
            headers=editor_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["provider"] is None
        assert "Title" in data["mapping"]
        assert data["mapping"]["Title"] is None

    def test_no_integration_mapping_keys_match_columns(self, client, editor_headers, db_session):
        from backend import models
        db_session.query(models.AIIntegration).update({"is_active": False})
        db_session.commit()

        cols = ["Title", "Author", "Year", "DOI"]
        resp = client.post(
            "/upload/suggest-mapping",
            json={"columns": cols, "sample_rows": []},
            headers=editor_headers,
        )
        assert resp.status_code == 200
        returned_keys = set(resp.json()["mapping"].keys())
        assert returned_keys == set(cols)

    def test_with_mock_adapter_returns_suggestions(self, client, editor_headers, db_session):
        from backend import models
        from backend.encryption import encrypt

        # Create an active integration
        integ = models.AIIntegration(
            provider_name="openai",
            model_name="gpt-4o-mini",
            api_key=encrypt("fake-key"),
            is_active=True,
        )
        db_session.add(integ)
        db_session.commit()

        mock_adapter = MagicMock()
        mock_adapter.provider_name = "openai"
        mock_adapter.chat.return_value = json.dumps({
            "Title": "primary_label",
            "Author": "secondary_label",
            "DOI": "enrichment_doi",
            "Unknown Col": None,
        })

        with patch("backend.analytics.rag_engine._build_adapter", return_value=mock_adapter):
            resp = client.post(
                "/upload/suggest-mapping",
                json={
                    "columns": ["Title", "Author", "DOI", "Unknown Col"],
                    "sample_rows": [{"Title": "My Paper", "Author": "Jane Doe", "DOI": "10.1/x", "Unknown Col": "xyz"}],
                },
                headers=editor_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["provider"] == "openai"
        assert data["mapping"]["Title"] == "primary_label"
        assert data["mapping"]["Author"] == "secondary_label"
        assert data["mapping"]["DOI"] == "enrichment_doi"
        assert data["mapping"]["Unknown Col"] is None

    def test_adapter_chat_exception_returns_null_mapping(self, client, editor_headers, db_session):
        from backend import models
        from backend.encryption import encrypt

        integ = models.AIIntegration(
            provider_name="openai",
            model_name="gpt-4o-mini",
            api_key=encrypt("fake-key"),
            is_active=True,
        )
        db_session.add(integ)
        db_session.commit()

        mock_adapter = MagicMock()
        mock_adapter.provider_name = "openai"
        mock_adapter.chat.side_effect = RuntimeError("Connection refused")

        with patch("backend.analytics.rag_engine._build_adapter", return_value=mock_adapter):
            resp = client.post(
                "/upload/suggest-mapping",
                json={"columns": ["Title"], "sample_rows": []},
                headers=editor_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["mapping"]["Title"] is None

    def test_missing_column_filled_with_null(self, client, editor_headers, db_session):
        """LLM omits a column entirely — endpoint must back-fill with null."""
        from backend import models
        from backend.encryption import encrypt

        integ = models.AIIntegration(
            provider_name="openai",
            model_name="gpt-4o-mini",
            api_key=encrypt("fake-key"),
            is_active=True,
        )
        db_session.add(integ)
        db_session.commit()

        mock_adapter = MagicMock()
        mock_adapter.provider_name = "openai"
        # LLM only returns mapping for Title, omits Author
        mock_adapter.chat.return_value = '{"Title": "primary_label"}'

        with patch("backend.analytics.rag_engine._build_adapter", return_value=mock_adapter):
            resp = client.post(
                "/upload/suggest-mapping",
                json={"columns": ["Title", "Author"], "sample_rows": []},
                headers=editor_headers,
            )

        data = resp.json()
        assert data["mapping"]["Title"] == "primary_label"
        assert "Author" in data["mapping"]
        assert data["mapping"]["Author"] is None

    def test_llm_unknown_field_coerced_to_null(self, client, editor_headers, db_session):
        from backend import models
        from backend.encryption import encrypt

        integ = models.AIIntegration(
            provider_name="anthropic",
            model_name="claude-3-5-haiku-latest",
            api_key=encrypt("fake-key"),
            is_active=True,
        )
        db_session.add(integ)
        db_session.commit()

        mock_adapter = MagicMock()
        mock_adapter.provider_name = "anthropic"
        mock_adapter.chat.return_value = '{"Title": "product_name_invented_by_llm"}'

        with patch("backend.analytics.rag_engine._build_adapter", return_value=mock_adapter):
            resp = client.post(
                "/upload/suggest-mapping",
                json={"columns": ["Title"], "sample_rows": []},
                headers=editor_headers,
            )

        assert resp.json()["mapping"]["Title"] is None


class TestScientificCoreColumnMapping:
    def test_scientific_identifiers_are_core_aliases(self):
        expected = {
            "DOI": "canonical_id",
            "ORCID": "canonical_id",
            "ROR": "canonical_id",
            "Title": "primary_label",
            "Author": "secondary_label",
            "Institution": "secondary_label",
            "Record ID": "canonical_id",
        }

        for column, target in expected.items():
            assert CORE_COLUMN_MAPPING[column] == target
            assert COLUMN_MAPPING[column] == target

    def test_commerce_aliases_are_compatibility_pack_only(self):
        assert "SKU" not in CORE_COLUMN_MAPPING
        assert COMMERCE_COLUMN_MAPPING["SKU"] == "canonical_id"
        assert COLUMN_MAPPING["SKU"] == "canonical_id"
