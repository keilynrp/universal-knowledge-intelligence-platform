import pytest
from unittest.mock import patch, MagicMock
from backend.adapters.enrichment.scopus import ScopusAdapter
from backend.schemas_enrichment import EnrichedRecord

class TestScopusAdapter:
    def test_inactive_without_api_key(self):
        adapter = ScopusAdapter()
        assert not adapter.is_active

    def test_active_with_api_key(self):
        adapter = ScopusAdapter(api_key="test_key")
        assert adapter.is_active

    @patch("backend.adapters.enrichment.scopus.httpx.Client.get")
    def test_search_by_title_success(self, mock_get):
        adapter = ScopusAdapter(api_key="test_key")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "search-results": {
                "entry": [
                    {
                        "dc:identifier": "SCOPUS_ID:12345",
                        "prism:doi": "10.1234/test",
                        "dc:title": "Test Publication",
                        "citedby-count": "42",
                        "dc:creator": "John Doe"
                    }
                ]
            }
        }
        mock_get.return_value = mock_response
        
        results = adapter.search_by_title("Test Publication")
        
        assert len(results) == 1
        record = results[0]
        assert record.title == "Test Publication"
        assert record.doi == "10.1234/test"
        assert record.citation_count == 42
        assert "John Doe" in record.authors
        assert "Scopus-Indexed" in record.concepts
        assert record.source_api == "Elsevier Scopus (Premium)"

    @patch("backend.adapters.enrichment.scopus.httpx.Client.get")
    def test_search_failed_auth(self, mock_get):
        adapter = ScopusAdapter(api_key="bad_key")
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        results = adapter.search_by_title("Test Publication")
        assert len(results) == 0

