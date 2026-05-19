"""
Tests for scientific connectors: Crossref, Semantic Scholar, DBLP, PubMed upgrade,
configurable cascade, extended field persistence, and provider health endpoint.
"""
import json
import os
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from backend.schemas_enrichment import EnrichedRecord


# ── 1. EnrichedRecord Extension ──────────────────────────────────────────────

class TestEnrichedRecordExtension:
    """Existing adapters produce valid EnrichedRecord without setting new fields."""

    def test_enriched_record_defaults(self):
        rec = EnrichedRecord(id="test-1", title="Test Paper", source_api="Test")
        assert rec.funding is None
        assert rec.references_count is None
        assert rec.tldr is None
        assert rec.influential_citation_count is None
        assert rec.license is None
        assert rec.mesh_terms is None
        assert rec.venue is None

    def test_enriched_record_with_extended_fields(self):
        rec = EnrichedRecord(
            id="test-2",
            title="Extended Paper",
            source_api="Test",
            funding=["NSF Grant 123"],
            references_count=42,
            tldr="A brief summary.",
            influential_citation_count=7,
            license="https://creativecommons.org/licenses/by/4.0/",
            mesh_terms=["Genomics", "RNA"],
            venue="Nature",
        )
        assert rec.funding == ["NSF Grant 123"]
        assert rec.references_count == 42
        assert rec.tldr == "A brief summary."
        assert rec.influential_citation_count == 7
        assert rec.license == "https://creativecommons.org/licenses/by/4.0/"
        assert rec.mesh_terms == ["Genomics", "RNA"]
        assert rec.venue == "Nature"


# ── 2. PubMed Adapter Upgrade ────────────────────────────────────────────────

class TestPubMedAdapter:
    def test_abc_compliance(self):
        from backend.adapters.enrichment.pubmed import PubMedAdapter
        from backend.adapters.enrichment.base import BaseScientometricAdapter
        assert issubclass(PubMedAdapter, BaseScientometricAdapter)

    def test_is_active(self):
        from backend.adapters.enrichment.pubmed import PubMedAdapter
        adapter = PubMedAdapter()
        assert adapter.is_active is True

    def test_search_by_doi_calls_esearch_with_doi_field(self):
        from backend.adapters.enrichment.pubmed import PubMedAdapter
        adapter = PubMedAdapter()
        with patch.object(adapter, "_esearch", return_value=[]) as mock_es:
            result = adapter.search_by_doi("10.1234/test")
            mock_es.assert_called_once_with("10.1234/test[DOI]", limit=1)
            assert result is None

    def test_search_by_title_delegates_to_search_bulk(self):
        from backend.adapters.enrichment.pubmed import PubMedAdapter
        adapter = PubMedAdapter()
        with patch.object(adapter, "search_bulk", return_value=[]) as mock_sb:
            result = adapter.search_by_title("Deep Learning", limit=3)
            mock_sb.assert_called_once_with("Deep Learning[Title]", limit=3)
            assert result == []

    def test_search_by_author_delegates_to_search_bulk(self):
        from backend.adapters.enrichment.pubmed import PubMedAdapter
        adapter = PubMedAdapter()
        with patch.object(adapter, "search_bulk", return_value=[]) as mock_sb:
            result = adapter.search_by_author("John Smith", limit=5)
            mock_sb.assert_called_once_with("John Smith[Author]", limit=5)
            assert result == []

    def test_mesh_terms_extraction(self):
        from backend.adapters.enrichment.pubmed import PubMedAdapter
        import xml.etree.ElementTree as ET

        xml = """<PubmedArticle>
          <MedlineCitation>
            <PMID>12345</PMID>
            <Article>
              <ArticleTitle>Test Article</ArticleTitle>
              <AuthorList/>
              <Journal><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue><Title>Test Journal</Title></Journal>
            </Article>
            <MeshHeadingList>
              <MeshHeading><DescriptorName>Genomics</DescriptorName></MeshHeading>
              <MeshHeading><DescriptorName>RNA, Messenger</DescriptorName></MeshHeading>
            </MeshHeadingList>
          </MedlineCitation>
          <PubmedData>
            <ArticleIdList>
              <ArticleId IdType="doi">10.1234/test</ArticleId>
            </ArticleIdList>
          </PubmedData>
        </PubmedArticle>"""

        adapter = PubMedAdapter()
        article_el = ET.fromstring(xml)
        rec = adapter._parse_article(article_el)
        assert rec is not None
        assert rec.mesh_terms == ["Genomics", "RNA, Messenger"]
        assert rec.venue == "Test Journal"
        assert rec.doi == "10.1234/test"

    def test_venue_extraction(self):
        from backend.adapters.enrichment.pubmed import PubMedAdapter
        import xml.etree.ElementTree as ET

        xml = """<PubmedArticle>
          <MedlineCitation>
            <PMID>99999</PMID>
            <Article>
              <ArticleTitle>Venue Test</ArticleTitle>
              <AuthorList/>
              <Journal><JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue><Title>The Lancet</Title></Journal>
            </Article>
          </MedlineCitation>
          <PubmedData><ArticleIdList/></PubmedData>
        </PubmedArticle>"""

        adapter = PubMedAdapter()
        article_el = ET.fromstring(xml)
        rec = adapter._parse_article(article_el)
        assert rec is not None
        assert rec.venue == "The Lancet"


# ── 3. Crossref Adapter ─────────────────────────────────────────────────────

class TestCrossrefAdapter:
    def test_abc_compliance(self):
        from backend.adapters.enrichment.crossref import CrossrefAdapter
        from backend.adapters.enrichment.base import BaseScientometricAdapter
        assert issubclass(CrossrefAdapter, BaseScientometricAdapter)

    def test_is_active(self):
        from backend.adapters.enrichment.crossref import CrossrefAdapter
        adapter = CrossrefAdapter()
        assert adapter.is_active is True

    def test_parse_record_funding(self):
        from backend.adapters.enrichment.crossref import CrossrefAdapter
        adapter = CrossrefAdapter()
        raw = {
            "DOI": "10.1234/test",
            "title": ["Funded Paper"],
            "author": [{"given": "Jane", "family": "Doe"}],
            "is-referenced-by-count": 10,
            "published-print": {"date-parts": [[2023]]},
            "funder": [{"name": "NSF"}, {"name": "NIH"}],
            "references-count": 30,
            "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/", "content-version": "vor"}],
            "container-title": ["Nature"],
        }
        rec = adapter._parse_record(raw)
        assert rec.funding == ["NSF", "NIH"]
        assert rec.references_count == 30
        assert rec.license == "https://creativecommons.org/licenses/by/4.0/"
        assert rec.venue == "Nature"
        assert rec.is_open_access is True

    def test_parse_record_no_funding(self):
        from backend.adapters.enrichment.crossref import CrossrefAdapter
        adapter = CrossrefAdapter()
        raw = {"DOI": "10.1234/nofund", "title": ["No Funds"]}
        rec = adapter._parse_record(raw)
        assert rec.funding is None

    def test_doi_lookup_404_returns_none(self):
        from backend.adapters.enrichment.crossref import CrossrefAdapter
        adapter = CrossrefAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch.object(adapter.client, "get", return_value=mock_resp):
            result = adapter.search_by_doi("10.9999/nonexistent")
            assert result is None

    def test_title_search_returns_records(self):
        from backend.adapters.enrichment.crossref import CrossrefAdapter
        adapter = CrossrefAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "items": [
                    {"DOI": "10.1234/a", "title": ["Paper A"]},
                    {"DOI": "10.1234/b", "title": ["Paper B"]},
                ]
            }
        }
        with patch.object(adapter.client, "get", return_value=mock_resp):
            results = adapter.search_by_title("test query")
            assert len(results) == 2
            assert results[0].doi == "10.1234/a"

    def test_error_429_raises(self):
        from backend.adapters.enrichment.crossref import CrossrefAdapter
        import httpx
        adapter = CrossrefAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=mock_resp
        )
        with patch.object(adapter.client, "get", return_value=mock_resp):
            with pytest.raises(httpx.HTTPStatusError):
                adapter.search_by_doi("10.1234/test")


# ── 4. Semantic Scholar Adapter ──────────────────────────────────────────────

class TestSemanticScholarAdapter:
    def test_abc_compliance(self):
        from backend.adapters.enrichment.semantic_scholar import SemanticScholarAdapter
        from backend.adapters.enrichment.base import BaseScientometricAdapter
        assert issubclass(SemanticScholarAdapter, BaseScientometricAdapter)

    def test_is_active(self):
        from backend.adapters.enrichment.semantic_scholar import SemanticScholarAdapter
        adapter = SemanticScholarAdapter()
        assert adapter.is_active is True

    def test_parse_record_tldr_and_influential(self):
        from backend.adapters.enrichment.semantic_scholar import SemanticScholarAdapter
        adapter = SemanticScholarAdapter()
        raw = {
            "paperId": "abc123",
            "title": "TLDR Paper",
            "authors": [{"name": "Alice"}],
            "year": 2024,
            "citationCount": 50,
            "influentialCitationCount": 12,
            "isOpenAccess": True,
            "tldr": {"text": "This paper introduces a new method."},
            "venue": "ICML",
            "externalIds": {"DOI": "10.1234/s2test"},
        }
        rec = adapter._parse_record(raw)
        assert rec.tldr == "This paper introduces a new method."
        assert rec.influential_citation_count == 12
        assert rec.venue == "ICML"
        assert rec.doi == "10.1234/s2test"

    def test_doi_lookup_404_returns_none(self):
        from backend.adapters.enrichment.semantic_scholar import SemanticScholarAdapter
        adapter = SemanticScholarAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch.object(adapter.client, "get", return_value=mock_resp):
            result = adapter.search_by_doi("10.9999/missing")
            assert result is None

    def test_title_search_returns_records(self):
        from backend.adapters.enrichment.semantic_scholar import SemanticScholarAdapter
        adapter = SemanticScholarAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {
                    "paperId": "p1",
                    "title": "Found Paper",
                    "authors": [],
                    "year": 2023,
                    "citationCount": 5,
                    "influentialCitationCount": 1,
                    "isOpenAccess": False,
                    "tldr": None,
                    "venue": "NeurIPS",
                    "externalIds": {},
                }
            ]
        }
        with patch.object(adapter.client, "get", return_value=mock_resp):
            results = adapter.search_by_title("test paper")
            assert len(results) == 1
            assert results[0].venue == "NeurIPS"

    def test_api_key_header(self):
        from backend.adapters.enrichment.semantic_scholar import SemanticScholarAdapter
        with patch.dict(os.environ, {"S2_API_KEY": "test-key-123"}):
            adapter = SemanticScholarAdapter()
            assert adapter.client.headers.get("x-api-key") == "test-key-123"


# ── 5. DBLP Adapter ─────────────────────────────────────────────────────────

class TestDBLPAdapter:
    def test_abc_compliance(self):
        from backend.adapters.enrichment.dblp import DBLPAdapter
        from backend.adapters.enrichment.base import BaseScientometricAdapter
        assert issubclass(DBLPAdapter, BaseScientometricAdapter)

    def test_is_active(self):
        from backend.adapters.enrichment.dblp import DBLPAdapter
        adapter = DBLPAdapter()
        assert adapter.is_active is True

    def test_parse_record_venue_extraction(self):
        from backend.adapters.enrichment.dblp import DBLPAdapter
        adapter = DBLPAdapter()
        hit = {
            "info": {
                "@id": "dblp-1",
                "title": "Test Paper.",
                "year": "2024",
                "venue": "SIGMOD",
                "authors": {"author": [{"text": "Bob Smith"}]},
                "ee": "https://doi.org/10.1234/dblp-test",
            }
        }
        rec = adapter._parse_record(hit)
        assert rec.venue == "SIGMOD"
        assert rec.doi == "10.1234/dblp-test"
        assert rec.title == "Test Paper"  # trailing period stripped
        assert rec.authors == ["Bob Smith"]

    def test_doi_extraction_from_list(self):
        from backend.adapters.enrichment.dblp import DBLPAdapter
        adapter = DBLPAdapter()
        doi = adapter._extract_doi(["https://arxiv.org/abs/1234", "https://doi.org/10.5678/test"])
        assert doi == "10.5678/test"

    def test_doi_extraction_none(self):
        from backend.adapters.enrichment.dblp import DBLPAdapter
        adapter = DBLPAdapter()
        assert adapter._extract_doi(None) is None
        assert adapter._extract_doi("https://example.com") is None

    def test_title_search_empty(self):
        from backend.adapters.enrichment.dblp import DBLPAdapter
        adapter = DBLPAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": {"hits": {"hit": []}}}
        with patch.object(adapter.client, "get", return_value=mock_resp):
            results = adapter.search_by_title("nonexistent paper")
            assert results == []

    def test_search_by_doi_matches(self):
        from backend.adapters.enrichment.dblp import DBLPAdapter
        adapter = DBLPAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "result": {
                "hits": {
                    "hit": [
                        {
                            "info": {
                                "@id": "hit1",
                                "title": "Wrong Paper",
                                "ee": "https://example.com",
                                "authors": {"author": []},
                            }
                        },
                        {
                            "info": {
                                "@id": "hit2",
                                "title": "Right Paper",
                                "ee": "https://doi.org/10.1234/target",
                                "authors": {"author": []},
                            }
                        },
                    ]
                }
            }
        }
        with patch.object(adapter.client, "get", return_value=mock_resp):
            result = adapter.search_by_doi("10.1234/target")
            assert result is not None
            assert result.title == "Right Paper"

    def test_error_429_raises(self):
        from backend.adapters.enrichment.dblp import DBLPAdapter
        import httpx
        adapter = DBLPAdapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=mock_resp
        )
        with patch.object(adapter.client, "get", return_value=mock_resp):
            with pytest.raises(httpx.HTTPStatusError):
                adapter.search_by_title("test")


# ── 6. Configurable Cascade ─────────────────────────────────────────────────

class TestConfigurableCascade:
    def test_default_cascade_order(self):
        from backend.enrichment_worker import _DEFAULT_CASCADE
        assert "openalex" in _DEFAULT_CASCADE
        assert "crossref" in _DEFAULT_CASCADE
        assert "pubmed" in _DEFAULT_CASCADE
        assert "semantic_scholar" in _DEFAULT_CASCADE
        assert "dblp" in _DEFAULT_CASCADE
        # BYOK first
        assert _DEFAULT_CASCADE.index("scopus") < _DEFAULT_CASCADE.index("openalex")

    def test_parse_cascade_custom(self):
        from backend.enrichment_worker import _parse_cascade
        with patch.dict(os.environ, {"ENRICHMENT_CASCADE": "crossref,openalex,dblp"}):
            result = _parse_cascade()
            assert result == ["crossref", "openalex", "dblp"]

    def test_parse_cascade_ignores_unknown(self):
        from backend.enrichment_worker import _parse_cascade
        with patch.dict(os.environ, {"ENRICHMENT_CASCADE": "crossref,fake_provider,openalex"}):
            result = _parse_cascade()
            assert result == ["crossref", "openalex"]

    def test_parse_cascade_all_invalid_falls_back(self):
        from backend.enrichment_worker import _parse_cascade, _DEFAULT_CASCADE
        with patch.dict(os.environ, {"ENRICHMENT_CASCADE": "fake1,fake2"}):
            result = _parse_cascade()
            assert result == _DEFAULT_CASCADE

    def test_provider_registry_contains_adapters(self):
        from backend.enrichment_worker import get_provider_registry
        reg = get_provider_registry()
        for name, (adapter, cb) in reg.items():
            if adapter is not None:
                assert hasattr(adapter, "search_by_title"), f"{name} adapter missing search_by_title"
                assert hasattr(cb, "call"), f"{name} circuit breaker missing call"


# ── 7. Extended Fields Persistence ───────────────────────────────────────────

class TestExtendedFieldsPersistence:
    def test_enrichment_persists_extended_fields(self, db_session, auth_headers, client):
        """When a provider returns extended fields, they end up in attributes_json."""
        from backend import models

        entity = models.RawEntity(
            primary_label="Extended Fields Test Paper",
            domain="default",
            enrichment_status="pending",
        )
        db_session.add(entity)
        db_session.commit()
        entity_id = entity.id

        mock_record = EnrichedRecord(
            id="ext-1",
            doi="10.1234/ext",
            title="Extended Fields Test Paper",
            source_api="Crossref",
            citation_count=10,
            funding=["NSF"],
            references_count=25,
            license="https://creativecommons.org/licenses/by/4.0/",
            venue="Science",
            tldr="A great paper.",
            influential_citation_count=3,
            mesh_terms=["Biology"],
        )

        with patch("backend.enrichment_worker._ACTIVE_CASCADE", ["crossref"]):
            with patch("backend.enrichment_worker._PROVIDER_MAP", {
                "crossref": (MagicMock(
                    is_active=True,
                    search_by_title=MagicMock(return_value=[mock_record]),
                ), MagicMock(call=lambda fn, *a, **kw: fn(*a, **kw))),
            }):
                from backend.enrichment_worker import enrich_single_record
                entity = db_session.get(models.RawEntity, entity_id)
                enrich_single_record(db_session, entity)

        db_session.refresh(entity)
        attrs = json.loads(entity.attributes_json or "{}")
        assert attrs.get("funding") == ["NSF"]
        assert attrs.get("references_count") == 25
        assert attrs.get("license") == "https://creativecommons.org/licenses/by/4.0/"
        assert attrs.get("venue") == "Science"
        assert attrs.get("tldr") == "A great paper."
        assert attrs.get("influential_citation_count") == 3
        assert attrs.get("mesh_terms") == ["Biology"]


# ── 8. Provider Health Endpoint ──────────────────────────────────────────────

class TestProviderHealthEndpoint:
    def test_endpoint_returns_providers(self, client, auth_headers):
        resp = client.get("/enrichment/providers", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        provider_names = [p["name"] for p in data]
        assert "openalex" in provider_names
        assert "crossref" in provider_names

    def test_endpoint_shows_circuit_state(self, client, auth_headers):
        resp = client.get("/enrichment/providers", headers=auth_headers)
        data = resp.json()
        for provider in data:
            assert "circuit_breaker" in provider
            cb = provider["circuit_breaker"]
            assert "state" in cb
            assert "failure_count" in cb
            assert "success_count" in cb


# ── 9. Circuit Breaker Introspection ─────────────────────────────────────────

class TestCircuitBreakerIntrospection:
    def test_failure_count_property(self):
        from backend.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(name="test", failure_threshold=3)
        assert cb.failure_count == 0
        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        except ValueError:
            pass
        assert cb.failure_count == 1

    def test_success_count_property(self):
        from backend.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(name="test", failure_threshold=3)
        assert cb.success_count == 0
        cb.call(lambda: "ok")
        assert cb.success_count == 1

    def test_last_failure_time_property(self):
        from backend.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(name="test", failure_threshold=3)
        assert cb.last_failure_time == 0.0
        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        except ValueError:
            pass
        assert cb.last_failure_time > 0.0
