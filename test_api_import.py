"""
Tests for scientific-import-api-sources change.
Covers:
  - OpenAlexAdapter.search_bulk (tasks 1.1–1.4)
  - PubMedAdapter.search_bulk   (tasks 2.1–2.5)
  - POST /import/openalex, POST /import/pubmed, GET /import/status (tasks 3.3–3.7)
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_openalex_work(title="Test Work", doi="10.1234/test", year=2022, cursor=None):
    return {
        "id": f"https://openalex.org/W{hash(title) % 1_000_000}",
        "doi": f"https://doi.org/{doi}",
        "display_name": title,
        "cited_by_count": 5,
        "publication_year": year,
        "open_access": {"is_oa": False},
        "authorships": [{"author": {"display_name": "Jane Doe"}}],
        "concepts": [{"display_name": "Knowledge Management", "score": 0.8}],
        "topics": [],
        "keywords": [],
        "primary_location": {"source": {"display_name": "Some Journal"}},
    }


def _openalex_page(works, next_cursor=None):
    return {"results": works, "meta": {"next_cursor": next_cursor, "count": len(works)}}


# ---------------------------------------------------------------------------
# 1.x  OpenAlexAdapter.search_bulk
# ---------------------------------------------------------------------------

class TestOpenAlexSearchBulk:
    def _adapter(self):
        from backend.adapters.enrichment.openalex import OpenAlexAdapter
        return OpenAlexAdapter(polite_email="test@example.com")

    def _mock_response(self, body: dict, status: int = 200):
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = body
        return resp

    def test_single_page_returns_records(self):
        adapter = self._adapter()
        works = [_make_openalex_work(f"Paper {i}", f"10.x/{i}") for i in range(5)]
        page = _openalex_page(works, next_cursor=None)

        with patch.object(adapter.client, "get", return_value=self._mock_response(page)):
            results = adapter.search_bulk("knowledge management", limit=10)

        assert len(results) == 5
        assert results[0].title == "Paper 0"
        assert results[0].authors == ["Jane Doe"]

    def test_multi_page_follows_cursor(self):
        adapter = self._adapter()
        page1 = _openalex_page(
            [_make_openalex_work(f"P{i}") for i in range(3)], next_cursor="abc"
        )
        page2 = _openalex_page(
            [_make_openalex_work(f"Q{i}") for i in range(2)], next_cursor=None
        )
        responses = iter([self._mock_response(page1), self._mock_response(page2)])

        with patch.object(adapter.client, "get", side_effect=lambda *a, **kw: next(responses)):
            with patch("time.sleep"):  # don't wait in tests
                results = adapter.search_bulk("test", limit=10)

        assert len(results) == 5

    def test_limit_cap_at_1000(self):
        adapter = self._adapter()
        # Returns 200 per page; limit capped at 1000
        big_page = _openalex_page(
            [_make_openalex_work(f"P{i}", f"10.x/{i}") for i in range(200)],
            next_cursor="next",
        )
        call_count = 0

        def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            params = kwargs.get("params", {})
            # After 5 pages (5*200=1000), cursor should stop being requested
            if call_count >= 5:
                return self._mock_response(_openalex_page([], next_cursor=None))
            return self._mock_response(big_page)

        with patch.object(adapter.client, "get", side_effect=fake_get):
            with patch("time.sleep"):
                results = adapter.search_bulk("test", limit=2000)

        assert len(results) <= 1000

    def test_empty_results(self):
        adapter = self._adapter()
        with patch.object(adapter.client, "get", return_value=self._mock_response(_openalex_page([]))):
            results = adapter.search_bulk("nothing here", limit=100)
        assert results == []

    def test_http_error_returns_empty(self):
        adapter = self._adapter()
        with patch.object(adapter.client, "get", return_value=self._mock_response({}, status=429)):
            results = adapter.search_bulk("test", limit=10)
        assert results == []

    def test_author_filter_sent_in_params(self):
        adapter = self._adapter()
        captured_params = {}

        def fake_get(url, params=None):
            captured_params.update(params or {})
            return self._mock_response(_openalex_page([]))

        with patch.object(adapter.client, "get", side_effect=fake_get):
            adapter.search_bulk("test", filters={"author": "Jane Doe"}, limit=5)

        assert "filter" in captured_params
        assert "author.display_name.search:Jane Doe" in captured_params["filter"]

    def test_issn_filter_sent_in_params(self):
        adapter = self._adapter()
        captured_params = {}

        def fake_get(url, params=None):
            captured_params.update(params or {})
            return self._mock_response(_openalex_page([]))

        with patch.object(adapter.client, "get", side_effect=fake_get):
            adapter.search_bulk("test", filters={"issn": "1234-5678"}, limit=5)

        assert "primary_location.source.issn:1234-5678" in captured_params.get("filter", "")

    def test_polite_mailto_in_params(self):
        adapter = self._adapter()
        captured_params = {}

        def fake_get(url, params=None):
            captured_params.update(params or {})
            return self._mock_response(_openalex_page([]))

        with patch.object(adapter.client, "get", side_effect=fake_get):
            adapter.search_bulk("test", limit=5)

        assert captured_params.get("mailto") == "test@example.com"


# ---------------------------------------------------------------------------
# 2.x  PubMedAdapter
# ---------------------------------------------------------------------------

_ESEARCH_XML = """<?xml version="1.0" ?>
<eSearchResult>
  <IdList>
    <Id>12345678</Id>
    <Id>87654321</Id>
  </IdList>
</eSearchResult>"""

_EFETCH_XML = """<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <ArticleTitle>Knowledge Sharing in Organizations</ArticleTitle>
        <Abstract><AbstractText>Abstract text here.</AbstractText></Abstract>
        <AuthorList>
          <Author><LastName>Smith</LastName><ForeName>John</ForeName></Author>
        </AuthorList>
        <Journal>
          <JournalIssue><PubDate><Year>2021</Year></PubDate></JournalIssue>
        </Journal>
        <AffiliationInfo><Affiliation>MIT, USA</Affiliation></AffiliationInfo>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1234/ks.2021.001</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>87654321</PMID>
      <Article>
        <ArticleTitle>Tacit Knowledge Transfer</ArticleTitle>
        <Abstract><AbstractText>Another abstract.</AbstractText></Abstract>
        <AuthorList>
          <Author><LastName>Lee</LastName><ForeName>Alice</ForeName></Author>
        </AuthorList>
        <Journal>
          <JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue>
        </Journal>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList/>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>"""


class TestPubMedAdapter:
    def _adapter(self):
        from backend.adapters.enrichment.pubmed import PubMedAdapter
        return PubMedAdapter()

    def _mock_get(self, esearch_text=_ESEARCH_XML, efetch_text=_EFETCH_XML):
        call_count = 0

        def fake_get(url, params=None, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.status_code = 200
            if "esearch" in url:
                resp.text = esearch_text
            else:
                resp.text = efetch_text
            return resp

        return fake_get

    def test_returns_parsed_records(self):
        adapter = self._adapter()
        with patch("requests.get", side_effect=self._mock_get()):
            with patch("time.sleep"):
                results = adapter.search_bulk("knowledge management", limit=10)

        assert len(results) == 2
        assert results[0].title == "Knowledge Sharing in Organizations"
        assert results[0].authors == ["Smith John"]
        assert results[0].doi == "10.1234/ks.2021.001"
        assert results[0].publication_year == 2021

    def test_missing_doi_handled_gracefully(self):
        adapter = self._adapter()
        with patch("requests.get", side_effect=self._mock_get()):
            with patch("time.sleep"):
                results = adapter.search_bulk("test", limit=10)

        # Second record has no DOI — should not raise, doi=None
        assert results[1].doi is None

    def test_limit_cap_at_500(self):
        adapter = self._adapter()
        # Even if caller passes 1000, adapter caps at 500
        big_esearch = """<?xml version="1.0"?><eSearchResult><IdList>
            """ + "".join(f"<Id>{i}</Id>" for i in range(600)) + """
        </IdList></eSearchResult>"""

        with patch("requests.get", side_effect=self._mock_get(esearch_text=big_esearch, efetch_text="<PubmedArticleSet/>")) as m:
            with patch("time.sleep"):
                adapter.search_bulk("test", limit=1000)

        # esearch retmax should have been 500 max
        esearch_call = m.call_args_list[0]
        params = esearch_call[1].get("params", esearch_call[0][1] if len(esearch_call[0]) > 1 else {})
        assert int(params.get("retmax", 0)) <= 500

    def test_empty_results(self):
        adapter = self._adapter()
        empty_xml = "<?xml version='1.0'?><eSearchResult><IdList/></eSearchResult>"
        with patch("requests.get", side_effect=self._mock_get(esearch_text=empty_xml)):
            with patch("time.sleep"):
                results = adapter.search_bulk("nothing", limit=10)
        assert results == []

    def test_rate_limit_delay_applied(self):
        adapter = self._adapter()
        sleep_calls = []

        with patch("requests.get", side_effect=self._mock_get()):
            with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
                adapter.search_bulk("test", limit=10)

        # At least one sleep call with ~1/3s default
        assert any(abs(s - (1 / 3)) < 0.05 for s in sleep_calls)


# ---------------------------------------------------------------------------
# 3.x  API import endpoints (integration)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """TestClient with auth headers (editor role)."""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    import os, bcrypt
    from backend.database import SessionLocal
    from backend import models

    db = SessionLocal()
    try:
        username = "apiimp_editor"
        pw = "testpassword"
        pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
        existing = db.query(models.User).filter_by(username=username).first()
        if not existing:
            user = models.User(
                username=username,
                email=f"{username}@test.local",
                password_hash=pw_hash,
                role="editor",
                is_active=True,
            )
            db.add(user)
            db.commit()
    finally:
        db.close()

    resp = client.post("/auth/token", data={"username": username, "password": pw})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestImportEndpoints:
    def test_openalex_import_returns_202(self, client, auth_headers):
        with patch("backend.routers.api_import.OpenAlexAdapter") as MockAdapter:
            mock_instance = MagicMock()
            mock_instance.search_bulk.return_value = []
            MockAdapter.return_value = mock_instance

            resp = client.post(
                "/import/openalex",
                json={"query": "knowledge management", "limit": 10},
                headers=auth_headers,
            )

        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "queued"

    def test_openalex_import_requires_auth(self, client):
        resp = client.post("/import/openalex", json={"query": "test", "limit": 10})
        assert resp.status_code == 401

    def test_pubmed_import_returns_202(self, client, auth_headers):
        with patch("backend.routers.api_import.PubMedAdapter") as MockAdapter:
            mock_instance = MagicMock()
            mock_instance.search_bulk.return_value = []
            MockAdapter.return_value = mock_instance

            resp = client.post(
                "/import/pubmed",
                json={"query": "knowledge transfer", "limit": 10},
                headers=auth_headers,
            )

        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body

    def test_pubmed_limit_over_500_rejected(self, client, auth_headers):
        resp = client.post(
            "/import/pubmed",
            json={"query": "test", "limit": 600},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_pubmed_import_requires_auth(self, client):
        resp = client.post("/import/pubmed", json={"query": "test", "limit": 10})
        assert resp.status_code == 401

    def test_import_status_unknown_job(self, client, auth_headers):
        resp = client.get("/import/status/nonexistent-job-id", headers=auth_headers)
        assert resp.status_code == 404

    def test_import_status_returns_job_state(self, client, auth_headers):
        # Start a job first
        with patch("backend.routers.api_import.OpenAlexAdapter") as MockAdapter:
            mock_instance = MagicMock()
            mock_instance.search_bulk.return_value = []
            MockAdapter.return_value = mock_instance

            resp = client.post(
                "/import/openalex",
                json={"query": "test", "limit": 5},
                headers=auth_headers,
            )

        job_id = resp.json()["job_id"]
        status_resp = client.get(f"/import/status/{job_id}", headers=auth_headers)
        assert status_resp.status_code == 200
        body = status_resp.json()
        assert body["job_id"] == job_id
        assert "status" in body
        assert "progress" in body
