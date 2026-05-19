# Scientific Connectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add native scientific API connectors (PubMed, CrossRef, arXiv, DataCite, Zotero, ORCID) that integrate seamlessly into the existing import wizard flow, allowing R&D users to search and import literature directly from within UKIP.

**Architecture:** New `backend/adapters/scientific/` package following the existing adapter pattern, a new `backend/routers/scientific_import.py` router, and a new frontend page `/import/scientific` that reuses the existing import pipeline. All new endpoints are additive — zero modification to the existing upload/enrichment paths.

**Tech Stack:** Python `httpx` (already installed), `xml.etree.ElementTree` (stdlib), existing `EnrichedRecord` + `science_record_to_entity()` pipeline, FastAPI router, Next.js + Tailwind frontend.

---

## File Map

### New files (create)
| Path | Responsibility |
|------|---------------|
| `backend/adapters/scientific/__init__.py` | Factory: `get_scientific_adapter(source, config)` |
| `backend/adapters/scientific/base.py` | Abstract `BaseScientificAdapter`: `search()`, `fetch_by_doi()`, `fetch_batch_dois()` |
| `backend/adapters/scientific/crossref.py` | CrossRef REST API — batch DOI resolution + title search |
| `backend/adapters/scientific/pubmed.py` | NCBI E-utilities — PubMed search + fetch by PMID |
| `backend/adapters/scientific/arxiv.py` | arXiv Atom API — full-text search |
| `backend/adapters/scientific/datacite.py` | DataCite REST API — dataset DOIs |
| `backend/adapters/scientific/zotero.py` | Zotero Web API — user/group library import (requires API key) |
| `backend/adapters/scientific/orcid_publications.py` | ORCID API — import all works by ORCID ID |
| `backend/routers/scientific_import.py` | New router: search, import, DOI batch, sources list |
| `backend/tests/test_scientific_import.py` | All tests for the new router + adapters |
| `frontend/app/import/scientific/page.tsx` | New import page: source picker → query → preview → import |

### Modified files (extend, no breaking changes)
| Path | Change |
|------|--------|
| `backend/main.py` | `include_router(scientific_import.router)` |
| `backend/adapters/scientific/__init__.py` | Factory registry |
| `frontend/app/components/Sidebar.tsx` | Add "Scientific Import" nav item under Import section |

---

## Task 1: Base Abstract Class

**Files:**
- Create: `backend/adapters/scientific/__init__.py`
- Create: `backend/adapters/scientific/base.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_scientific_import.py
import pytest
from backend.adapters.scientific.base import BaseScientificAdapter, ScientificRecord

def test_scientific_record_has_required_fields():
    r = ScientificRecord(
        source_api="test",
        title="Test paper",
        doi="10.1234/test",
        authors=["Smith, J."],
        year=2023,
        abstract="A test.",
        concepts=["biology"],
        citation_count=5,
        url="https://doi.org/10.1234/test",
        raw_response={},
    )
    assert r.title == "Test paper"
    assert r.doi == "10.1234/test"
    assert r.source_api == "test"

def test_base_adapter_is_abstract():
    with pytest.raises(TypeError):
        BaseScientificAdapter()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd D:/universal-knowledge-intelligence-platform
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py::test_scientific_record_has_required_fields -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create the package and base class**

```python
# backend/adapters/scientific/__init__.py
from backend.adapters.scientific.base import BaseScientificAdapter, ScientificRecord

_REGISTRY: dict = {}

def register(name: str, cls):
    _REGISTRY[name] = cls

def get_scientific_adapter(source: str, config: dict = None) -> "BaseScientificAdapter":
    if source not in _REGISTRY:
        raise ValueError(f"Unknown scientific source: '{source}'. Available: {list(_REGISTRY)}")
    return _REGISTRY[source](config or {})

def list_sources() -> list[dict]:
    return [
        {"id": k, "name": v.DISPLAY_NAME, "requires_key": v.REQUIRES_API_KEY}
        for k, v in _REGISTRY.items()
    ]
```

```python
# backend/adapters/scientific/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ScientificRecord:
    source_api: str
    title: str
    doi: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    abstract: Optional[str] = None
    journal: Optional[str] = None
    publisher: Optional[str] = None
    concepts: list[str] = field(default_factory=list)
    citation_count: int = 0
    is_open_access: bool = False
    url: Optional[str] = None
    external_id: Optional[str] = None   # PMID, arXiv ID, etc.
    raw_response: dict = field(default_factory=dict)

class BaseScientificAdapter(ABC):
    DISPLAY_NAME: str = "Unknown"
    REQUIRES_API_KEY: bool = False

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def search(self, query: str, max_results: int = 20) -> list[ScientificRecord]:
        """Free-text search. Returns up to max_results records."""

    @abstractmethod
    def fetch_by_doi(self, doi: str) -> Optional[ScientificRecord]:
        """Fetch a single record by DOI. Returns None if not found."""

    def fetch_batch_dois(self, dois: list[str]) -> list[ScientificRecord]:
        """Fetch multiple DOIs. Default: sequential calls to fetch_by_doi."""
        results = []
        for doi in dois:
            rec = self.fetch_by_doi(doi.strip())
            if rec:
                results.append(rec)
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py::test_scientific_record_has_required_fields backend/tests/test_scientific_import.py::test_base_adapter_is_abstract -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/scientific/
git commit -m "feat: add scientific adapter base class and factory"
```

---

## Task 2: CrossRef Adapter (Quick Win — no API key needed)

**Files:**
- Create: `backend/adapters/scientific/crossref.py`
- Modify: `backend/adapters/scientific/__init__.py` (add import + register call)

- [ ] **Step 1: Write the failing tests**

```python
# Add to backend/tests/test_scientific_import.py
from unittest.mock import patch, MagicMock
from backend.adapters.scientific.crossref import CrossRefAdapter

CROSSREF_WORK_FIXTURE = {
    "message": {
        "items": [{
            "DOI": "10.1038/nature12373",
            "title": ["Cas9 as a genome editing tool"],
            "author": [{"family": "Cong", "given": "L."}],
            "published": {"date-parts": [[2013]]},
            "abstract": "CRISPR abstract here.",
            "subject": ["Genetics"],
            "is-referenced-by-count": 9000,
            "publisher": "Nature Publishing Group",
            "container-title": ["Nature"],
            "URL": "https://doi.org/10.1038/nature12373",
        }]
    }
}

CROSSREF_DOI_FIXTURE = {
    "message": {
        "DOI": "10.1038/nature12373",
        "title": ["Cas9 as a genome editing tool"],
        "author": [{"family": "Cong", "given": "L."}],
        "published": {"date-parts": [[2013]]},
        "abstract": "CRISPR abstract.",
        "subject": ["Genetics"],
        "is-referenced-by-count": 9000,
        "publisher": "Nature Publishing Group",
        "container-title": ["Nature"],
        "URL": "https://doi.org/10.1038/nature12373",
    }
}

def test_crossref_search_returns_records():
    adapter = CrossRefAdapter({})
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = CROSSREF_WORK_FIXTURE
        mock_get.return_value = mock_resp
        results = adapter.search("CRISPR", max_results=5)
    assert len(results) == 1
    assert results[0].doi == "10.1038/nature12373"
    assert results[0].source_api == "crossref"
    assert results[0].citation_count == 9000

def test_crossref_fetch_by_doi():
    adapter = CrossRefAdapter({})
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = CROSSREF_DOI_FIXTURE
        mock_get.return_value = mock_resp
        rec = adapter.fetch_by_doi("10.1038/nature12373")
    assert rec is not None
    assert rec.title == "Cas9 as a genome editing tool"
    assert rec.authors == ["Cong, L."]

def test_crossref_fetch_by_doi_not_found():
    adapter = CrossRefAdapter({})
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp
        rec = adapter.fetch_by_doi("10.9999/doesnotexist")
    assert rec is None

def test_crossref_registered_in_factory():
    from backend.adapters.scientific import list_sources
    sources = list_sources()
    ids = [s["id"] for s in sources]
    assert "crossref" in ids
```

- [ ] **Step 2: Run tests to see them fail**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "crossref" -v
```
Expected: 4 FAILs (ImportError)

- [ ] **Step 3: Implement CrossRefAdapter**

```python
# backend/adapters/scientific/crossref.py
import httpx
from typing import Optional
from backend.adapters.scientific.base import BaseScientificAdapter, ScientificRecord

class CrossRefAdapter(BaseScientificAdapter):
    DISPLAY_NAME = "CrossRef"
    REQUIRES_API_KEY = False
    BASE_URL = "https://api.crossref.org"

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = httpx.Client(timeout=15.0, headers={"User-Agent": "UKIP/1.0 (mailto:research@ukip.dev)"})

    def _parse_work(self, item: dict) -> ScientificRecord:
        doi = (item.get("DOI") or "").strip()
        titles = item.get("title") or []
        title = titles[0] if titles else "Untitled"
        authors = [
            f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
            for a in item.get("author") or []
        ]
        date_parts = (item.get("published") or item.get("created") or {}).get("date-parts", [[]])
        year = date_parts[0][0] if date_parts and date_parts[0] else None
        journals = item.get("container-title") or []
        return ScientificRecord(
            source_api="crossref",
            title=title,
            doi=doi,
            authors=authors,
            year=year,
            abstract=item.get("abstract"),
            journal=journals[0] if journals else None,
            publisher=item.get("publisher"),
            concepts=item.get("subject") or [],
            citation_count=item.get("is-referenced-by-count", 0),
            url=item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
            raw_response=item,
        )

    def search(self, query: str, max_results: int = 20) -> list[ScientificRecord]:
        resp = self._client.get(
            f"{self.BASE_URL}/works",
            params={"query": query, "rows": min(max_results, 100), "select": "DOI,title,author,published,abstract,subject,is-referenced-by-count,publisher,container-title,URL"},
        )
        if resp.status_code != 200:
            return []
        items = resp.json().get("message", {}).get("items", [])
        return [self._parse_work(i) for i in items]

    def fetch_by_doi(self, doi: str) -> Optional[ScientificRecord]:
        import urllib.parse
        resp = self._client.get(f"{self.BASE_URL}/works/{urllib.parse.quote(doi, safe='')}")
        if resp.status_code != 200:
            return None
        return self._parse_work(resp.json().get("message", {}))
```

Then update `__init__.py` to register:
```python
# Add at bottom of backend/adapters/scientific/__init__.py
from backend.adapters.scientific.crossref import CrossRefAdapter
register("crossref", CrossRefAdapter)
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "crossref" -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/scientific/crossref.py backend/adapters/scientific/__init__.py backend/tests/test_scientific_import.py
git commit -m "feat: add CrossRef scientific adapter"
```

---

## Task 3: PubMed Adapter

**Files:**
- Create: `backend/adapters/scientific/pubmed.py`
- Modify: `backend/adapters/scientific/__init__.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to test_scientific_import.py
from backend.adapters.scientific.pubmed import PubMedAdapter

PUBMED_SEARCH_FIXTURE = {"esearchresult": {"idlist": ["37001234", "37001235"]}}

PUBMED_FETCH_FIXTURE = {
    "result": {
        "37001234": {
            "uid": "37001234",
            "title": "CRISPR therapeutic advances",
            "authors": [{"name": "Zhang, F"}],
            "pubdate": "2023",
            "source": "Nature Medicine",
            "elocationid": "doi: 10.1038/s41591-023-01234-5",
            "abstract": "CRISPR advances abstract.",
            "meshterms": [{"descriptorname": "Gene Editing"}],
            "articleids": [{"idtype": "doi", "value": "10.1038/s41591-023-01234-5"}],
        }
    }
}

def test_pubmed_search_returns_records():
    adapter = PubMedAdapter({})
    with patch("httpx.Client.get") as mock_get:
        def side_effect(url, **kwargs):
            m = MagicMock()
            m.status_code = 200
            if "esearch" in url:
                m.json.return_value = PUBMED_SEARCH_FIXTURE
            else:
                m.json.return_value = PUBMED_FETCH_FIXTURE
            return m
        mock_get.side_effect = side_effect
        results = adapter.search("CRISPR therapy", max_results=5)
    assert len(results) >= 1
    assert results[0].source_api == "pubmed"
    assert results[0].external_id == "37001234"

def test_pubmed_registered():
    from backend.adapters.scientific import list_sources
    ids = [s["id"] for s in list_sources()]
    assert "pubmed" in ids
```

- [ ] **Step 2: Run tests to see them fail**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "pubmed" -v
```
Expected: FAILs

- [ ] **Step 3: Implement PubMedAdapter**

```python
# backend/adapters/scientific/pubmed.py
import httpx
from typing import Optional
from backend.adapters.scientific.base import BaseScientificAdapter, ScientificRecord

class PubMedAdapter(BaseScientificAdapter):
    DISPLAY_NAME = "PubMed / NCBI"
    REQUIRES_API_KEY = False   # Optional: api_key in config raises rate limit
    SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    FETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = httpx.Client(timeout=15.0)
        self._api_key = config.get("api_key")  # Optional — 10 req/s without, 100/s with

    def _base_params(self) -> dict:
        p = {"db": "pubmed", "retmode": "json"}
        if self._api_key:
            p["api_key"] = self._api_key
        return p

    def _parse_summary(self, uid: str, item: dict) -> ScientificRecord:
        doi = next(
            (a["value"] for a in item.get("articleids", []) if a.get("idtype") == "doi"),
            None,
        )
        authors = [a.get("name", "") for a in item.get("authors", [])]
        year_raw = item.get("pubdate", "")
        year = int(year_raw[:4]) if year_raw[:4].isdigit() else None
        mesh = [m.get("descriptorname", "") for m in item.get("meshterms", [])]
        return ScientificRecord(
            source_api="pubmed",
            title=item.get("title", "Untitled"),
            doi=doi,
            authors=authors,
            year=year,
            abstract=item.get("abstract"),
            journal=item.get("source"),
            concepts=mesh,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
            external_id=uid,
            raw_response=item,
        )

    def search(self, query: str, max_results: int = 20) -> list[ScientificRecord]:
        params = {**self._base_params(), "term": query, "retmax": min(max_results, 200)}
        search_resp = self._client.get(self.SEARCH_URL, params=params)
        if search_resp.status_code != 200:
            return []
        ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        return self._fetch_summaries(ids)

    def _fetch_summaries(self, ids: list[str]) -> list[ScientificRecord]:
        params = {**self._base_params(), "id": ",".join(ids)}
        resp = self._client.get(self.FETCH_URL, params=params)
        if resp.status_code != 200:
            return []
        result = resp.json().get("result", {})
        return [self._parse_summary(uid, result[uid]) for uid in ids if uid in result]

    def fetch_by_doi(self, doi: str) -> Optional[ScientificRecord]:
        params = {**self._base_params(), "term": f"{doi}[doi]", "retmax": 1}
        resp = self._client.get(self.SEARCH_URL, params=params)
        if resp.status_code != 200:
            return None
        ids = resp.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return None
        records = self._fetch_summaries([ids[0]])
        return records[0] if records else None
```

Register in `__init__.py`:
```python
from backend.adapters.scientific.pubmed import PubMedAdapter
register("pubmed", PubMedAdapter)
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "pubmed" -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/scientific/pubmed.py backend/adapters/scientific/__init__.py backend/tests/test_scientific_import.py
git commit -m "feat: add PubMed scientific adapter"
```

---

## Task 4: arXiv Adapter

**Files:**
- Create: `backend/adapters/scientific/arxiv.py`
- Modify: `backend/adapters/scientific/__init__.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to test_scientific_import.py
from backend.adapters.scientific.arxiv import ArXivAdapter

ARXIV_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <title>Attention Is All You Need Redux</title>
    <summary>A revisit of transformers.</summary>
    <published>2023-01-01T00:00:00Z</published>
    <author><name>Vaswani, A.</name></author>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
    <link href="https://arxiv.org/abs/2301.00001" rel="alternate" type="text/html"/>
    <arxiv:doi xmlns:arxiv="http://arxiv.org/schemas/atom">10.48550/arXiv.2301.00001</arxiv:doi>
  </entry>
</feed>"""

def test_arxiv_search_returns_records():
    adapter = ArXivAdapter({})
    with patch("httpx.Client.get") as mock_get:
        m = MagicMock()
        m.status_code = 200
        m.text = ARXIV_XML
        mock_get.return_value = m
        results = adapter.search("transformers attention", max_results=5)
    assert len(results) == 1
    assert results[0].source_api == "arxiv"
    assert "Vaswani" in results[0].authors[0]
    assert results[0].year == 2023

def test_arxiv_registered():
    from backend.adapters.scientific import list_sources
    ids = [s["id"] for s in list_sources()]
    assert "arxiv" in ids
```

- [ ] **Step 2: Run to fail**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "arxiv" -v
```

- [ ] **Step 3: Implement ArXivAdapter**

```python
# backend/adapters/scientific/arxiv.py
import httpx
import xml.etree.ElementTree as ET
from typing import Optional
from backend.adapters.scientific.base import BaseScientificAdapter, ScientificRecord

_ATOM = "http://www.w3.org/2005/Atom"
_ARXIV = "http://arxiv.org/schemas/atom"

class ArXivAdapter(BaseScientificAdapter):
    DISPLAY_NAME = "arXiv"
    REQUIRES_API_KEY = False
    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = httpx.Client(timeout=15.0)

    def _parse_entry(self, entry) -> ScientificRecord:
        ns = {"a": _ATOM, "arxiv": _ARXIV}
        title = (entry.findtext(f"{{{_ATOM}}}title") or "").strip().replace("\n", " ")
        abstract = (entry.findtext(f"{{{_ATOM}}}summary") or "").strip()
        published = entry.findtext(f"{{{_ATOM}}}published") or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        authors = [
            a.findtext(f"{{{_ATOM}}}name") or ""
            for a in entry.findall(f"{{{_ATOM}}}author")
        ]
        categories = [
            c.get("term", "")
            for c in entry.findall(f"{{{_ATOM}}}category")
        ]
        doi_el = entry.find(f"{{{_ARXIV}}}doi")
        doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None
        link = next(
            (l.get("href") for l in entry.findall(f"{{{_ATOM}}}link") if l.get("rel") == "alternate"),
            None,
        )
        arxiv_id = (entry.findtext(f"{{{_ATOM}}}id") or "").split("/abs/")[-1]
        return ScientificRecord(
            source_api="arxiv",
            title=title,
            doi=doi,
            authors=authors,
            year=year,
            abstract=abstract,
            concepts=categories,
            url=link,
            external_id=arxiv_id,
            raw_response={"id": arxiv_id, "categories": categories},
        )

    def search(self, query: str, max_results: int = 20) -> list[ScientificRecord]:
        resp = self._client.get(
            self.BASE_URL,
            params={"search_query": f"all:{query}", "max_results": min(max_results, 100), "sortBy": "relevance"},
        )
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        return [self._parse_entry(e) for e in root.findall(f"{{{_ATOM}}}entry")]

    def fetch_by_doi(self, doi: str) -> Optional[ScientificRecord]:
        # arXiv DOIs follow pattern 10.48550/arXiv.XXXX.XXXXX
        arxiv_id = doi.split("arXiv.")[-1] if "arXiv." in doi else None
        query = f"id:{arxiv_id}" if arxiv_id else f"all:{doi}"
        resp = self._client.get(self.BASE_URL, params={"search_query": query, "max_results": 1})
        if resp.status_code != 200:
            return None
        root = ET.fromstring(resp.text)
        entries = root.findall(f"{{{_ATOM}}}entry")
        return self._parse_entry(entries[0]) if entries else None
```

Register:
```python
from backend.adapters.scientific.arxiv import ArXivAdapter
register("arxiv", ArXivAdapter)
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "arxiv" -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/scientific/arxiv.py backend/adapters/scientific/__init__.py backend/tests/test_scientific_import.py
git commit -m "feat: add arXiv scientific adapter"
```

---

## Task 5: DataCite Adapter

**Files:**
- Create: `backend/adapters/scientific/datacite.py`
- Modify: `backend/adapters/scientific/__init__.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to test_scientific_import.py
from backend.adapters.scientific.datacite import DataCiteAdapter

DATACITE_FIXTURE = {
    "data": [{
        "id": "10.5281/zenodo.1234567",
        "attributes": {
            "doi": "10.5281/zenodo.1234567",
            "titles": [{"title": "Climate dataset 2020"}],
            "creators": [{"name": "Doe, Jane", "nameType": "Personal"}],
            "publicationYear": 2020,
            "descriptions": [{"description": "Dataset of climate measurements.", "descriptionType": "Abstract"}],
            "subjects": [{"subject": "Climate Science"}],
            "publisher": "Zenodo",
            "url": "https://zenodo.org/record/1234567",
            "citationCount": 12,
        }
    }]
}

def test_datacite_search_returns_records():
    adapter = DataCiteAdapter({})
    with patch("httpx.Client.get") as mock_get:
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = DATACITE_FIXTURE
        mock_get.return_value = m
        results = adapter.search("climate dataset", max_results=5)
    assert len(results) == 1
    assert results[0].source_api == "datacite"
    assert results[0].doi == "10.5281/zenodo.1234567"
    assert results[0].year == 2020

def test_datacite_registered():
    from backend.adapters.scientific import list_sources
    ids = [s["id"] for s in list_sources()]
    assert "datacite" in ids
```

- [ ] **Step 2: Run to fail**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "datacite" -v
```

- [ ] **Step 3: Implement DataCiteAdapter**

```python
# backend/adapters/scientific/datacite.py
import httpx
from typing import Optional
from backend.adapters.scientific.base import BaseScientificAdapter, ScientificRecord

class DataCiteAdapter(BaseScientificAdapter):
    DISPLAY_NAME = "DataCite"
    REQUIRES_API_KEY = False
    BASE_URL = "https://api.datacite.org"

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = httpx.Client(timeout=15.0)

    def _parse_attrs(self, item: dict) -> ScientificRecord:
        attrs = item.get("attributes", {})
        doi = attrs.get("doi") or item.get("id", "")
        titles = attrs.get("titles") or []
        title = titles[0].get("title", "Untitled") if titles else "Untitled"
        creators = attrs.get("creators") or []
        authors = [c.get("name", "") for c in creators]
        subjects = attrs.get("subjects") or []
        concepts = [s.get("subject", "") for s in subjects]
        descriptions = attrs.get("descriptions") or []
        abstract = next(
            (d["description"] for d in descriptions if d.get("descriptionType") == "Abstract"),
            None,
        )
        return ScientificRecord(
            source_api="datacite",
            title=title,
            doi=doi,
            authors=authors,
            year=attrs.get("publicationYear"),
            abstract=abstract,
            publisher=attrs.get("publisher"),
            concepts=concepts,
            citation_count=attrs.get("citationCount", 0),
            url=attrs.get("url"),
            raw_response=attrs,
        )

    def search(self, query: str, max_results: int = 20) -> list[ScientificRecord]:
        resp = self._client.get(
            f"{self.BASE_URL}/works",
            params={"query": query, "page[size]": min(max_results, 100)},
        )
        if resp.status_code != 200:
            return []
        return [self._parse_attrs(i) for i in resp.json().get("data", [])]

    def fetch_by_doi(self, doi: str) -> Optional[ScientificRecord]:
        import urllib.parse
        resp = self._client.get(f"{self.BASE_URL}/works/{urllib.parse.quote(doi, safe='')}")
        if resp.status_code != 200:
            return None
        data = resp.json().get("data")
        return self._parse_attrs(data) if data else None
```

Register:
```python
from backend.adapters.scientific.datacite import DataCiteAdapter
register("datacite", DataCiteAdapter)
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "datacite" -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/scientific/datacite.py backend/adapters/scientific/__init__.py backend/tests/test_scientific_import.py
git commit -m "feat: add DataCite scientific adapter"
```

---

## Task 6: Zotero Adapter

**Files:**
- Create: `backend/adapters/scientific/zotero.py`
- Modify: `backend/adapters/scientific/__init__.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to test_scientific_import.py
from backend.adapters.scientific.zotero import ZoteroAdapter

ZOTERO_ITEM_FIXTURE = [{
    "data": {
        "key": "ABC12345",
        "itemType": "journalArticle",
        "title": "Zotero-indexed paper",
        "creators": [{"creatorType": "author", "lastName": "García", "firstName": "M."}],
        "date": "2022",
        "DOI": "10.1016/j.cell.2022.01.001",
        "abstractNote": "An abstract about cells.",
        "tags": [{"tag": "molecular biology"}],
        "publicationTitle": "Cell",
        "url": "https://doi.org/10.1016/j.cell.2022.01.001",
    }
}]

def test_zotero_requires_api_key():
    from backend.adapters.scientific.zotero import ZoteroAdapter
    assert ZoteroAdapter.REQUIRES_API_KEY is True

def test_zotero_search_returns_records():
    adapter = ZoteroAdapter({"api_key": "testkey123", "library_id": "12345", "library_type": "user"})
    with patch("httpx.Client.get") as mock_get:
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = ZOTERO_ITEM_FIXTURE
        mock_get.return_value = m
        results = adapter.search("cells", max_results=5)
    assert len(results) == 1
    assert results[0].source_api == "zotero"
    assert results[0].doi == "10.1016/j.cell.2022.01.001"

def test_zotero_registered():
    from backend.adapters.scientific import list_sources
    ids = [s["id"] for s in list_sources()]
    assert "zotero" in ids
```

- [ ] **Step 2: Run to fail**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "zotero" -v
```

- [ ] **Step 3: Implement ZoteroAdapter**

```python
# backend/adapters/scientific/zotero.py
import httpx
from typing import Optional
from backend.adapters.scientific.base import BaseScientificAdapter, ScientificRecord

class ZoteroAdapter(BaseScientificAdapter):
    DISPLAY_NAME = "Zotero"
    REQUIRES_API_KEY = True
    BASE_URL = "https://api.zotero.org"

    def __init__(self, config: dict):
        super().__init__(config)
        self._api_key = config.get("api_key", "")
        self._library_id = config.get("library_id", "")
        self._library_type = config.get("library_type", "user")  # "user" or "group"
        self._client = httpx.Client(
            timeout=15.0,
            headers={"Zotero-API-Version": "3", "Authorization": f"Bearer {self._api_key}"},
        )

    @property
    def _lib_path(self) -> str:
        return f"{self._library_type}s/{self._library_id}"

    def _parse_item(self, item: dict) -> ScientificRecord:
        data = item.get("data", {})
        creators = data.get("creators") or []
        authors = [
            f"{c.get('lastName', '')}, {c.get('firstName', '')}".strip(", ")
            for c in creators if c.get("creatorType") == "author"
        ]
        tags = [t.get("tag", "") for t in data.get("tags") or []]
        date_str = data.get("date", "")
        year = int(date_str[:4]) if date_str[:4].isdigit() else None
        return ScientificRecord(
            source_api="zotero",
            title=data.get("title", "Untitled"),
            doi=data.get("DOI"),
            authors=authors,
            year=year,
            abstract=data.get("abstractNote"),
            journal=data.get("publicationTitle"),
            publisher=data.get("publisher"),
            concepts=tags,
            url=data.get("url"),
            external_id=data.get("key"),
            raw_response=data,
        )

    def search(self, query: str, max_results: int = 20) -> list[ScientificRecord]:
        resp = self._client.get(
            f"{self.BASE_URL}/{self._lib_path}/items",
            params={"q": query, "limit": min(max_results, 100), "itemType": "-attachment"},
        )
        if resp.status_code != 200:
            return []
        return [self._parse_item(i) for i in resp.json()]

    def fetch_by_doi(self, doi: str) -> Optional[ScientificRecord]:
        results = self.search(doi, max_results=1)
        return results[0] if results else None
```

Register:
```python
from backend.adapters.scientific.zotero import ZoteroAdapter
register("zotero", ZoteroAdapter)
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "zotero" -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/scientific/zotero.py backend/adapters/scientific/__init__.py backend/tests/test_scientific_import.py
git commit -m "feat: add Zotero scientific adapter"
```

---

## Task 7: ORCID Publications Adapter

**Files:**
- Create: `backend/adapters/scientific/orcid_publications.py`
- Modify: `backend/adapters/scientific/__init__.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to test_scientific_import.py
from backend.adapters.scientific.orcid_publications import OrcidPublicationsAdapter

ORCID_WORKS_FIXTURE = {
    "group": [{
        "work-summary": [{
            "put-code": 98765,
            "title": {"title": {"value": "ORCID-tracked paper"}},
            "external-ids": {"external-id": [{"external-id-type": "doi", "external-id-value": "10.1007/s12345"}]},
            "publication-date": {"year": {"value": "2021"}},
            "journal-title": {"value": "Science"},
            "source": {"source-name": {"value": "CrossRef"}},
        }]
    }]
}

def test_orcid_search_by_orcid_id():
    adapter = OrcidPublicationsAdapter({})
    with patch("httpx.Client.get") as mock_get:
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = ORCID_WORKS_FIXTURE
        mock_get.return_value = m
        results = adapter.search("0000-0002-1825-0097", max_results=20)
    assert len(results) == 1
    assert results[0].source_api == "orcid"
    assert results[0].doi == "10.1007/s12345"

def test_orcid_registered():
    from backend.adapters.scientific import list_sources
    ids = [s["id"] for s in list_sources()]
    assert "orcid" in ids
```

- [ ] **Step 2: Run to fail**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "orcid" -v
```

- [ ] **Step 3: Implement OrcidPublicationsAdapter**

```python
# backend/adapters/scientific/orcid_publications.py
"""
ORCID adapter: `query` is treated as an ORCID iD (0000-0002-1825-0097).
Fetches all works associated with that researcher.
"""
import httpx
from typing import Optional
from backend.adapters.scientific.base import BaseScientificAdapter, ScientificRecord

class OrcidPublicationsAdapter(BaseScientificAdapter):
    DISPLAY_NAME = "ORCID Publications"
    REQUIRES_API_KEY = False
    BASE_URL = "https://pub.orcid.org/v3.0"

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = httpx.Client(
            timeout=20.0,
            headers={"Accept": "application/json"},
        )

    def _parse_summary(self, summary: dict) -> Optional[ScientificRecord]:
        title_obj = summary.get("title") or {}
        title = (title_obj.get("title") or {}).get("value", "Untitled")
        ext_ids = (summary.get("external-ids") or {}).get("external-id") or []
        doi = next(
            (e["external-id-value"] for e in ext_ids if e.get("external-id-type") == "doi"),
            None,
        )
        pub_date = summary.get("publication-date") or {}
        year_obj = pub_date.get("year") or {}
        year = int(year_obj["value"]) if year_obj.get("value", "").isdigit() else None
        journal_obj = summary.get("journal-title") or {}
        return ScientificRecord(
            source_api="orcid",
            title=title,
            doi=doi,
            year=year,
            journal=journal_obj.get("value"),
            external_id=str(summary.get("put-code", "")),
            url=f"https://doi.org/{doi}" if doi else None,
            raw_response=summary,
        )

    def search(self, query: str, max_results: int = 50) -> list[ScientificRecord]:
        """query = ORCID iD string."""
        orcid_id = query.strip()
        resp = self._client.get(f"{self.BASE_URL}/{orcid_id}/works")
        if resp.status_code != 200:
            return []
        groups = resp.json().get("group") or []
        results = []
        for group in groups[:max_results]:
            summaries = group.get("work-summary") or []
            if summaries:
                rec = self._parse_summary(summaries[0])
                if rec:
                    results.append(rec)
        return results

    def fetch_by_doi(self, doi: str) -> Optional[ScientificRecord]:
        # ORCID is not a DOI resolver — not the right tool for this
        return None
```

Register:
```python
from backend.adapters.scientific.orcid_publications import OrcidPublicationsAdapter
register("orcid", OrcidPublicationsAdapter)
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "orcid" -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/scientific/orcid_publications.py backend/adapters/scientific/__init__.py backend/tests/test_scientific_import.py
git commit -m "feat: add ORCID publications adapter"
```

---

## Task 8: Scientific Import Router

**Files:**
- Create: `backend/routers/scientific_import.py`
- Modify: `backend/main.py`

This router converts `ScientificRecord` objects into `RawEntity` rows using the **existing** `science_record_to_entity()` pipeline.

- [ ] **Step 1: Write failing tests**

```python
# Add to test_scientific_import.py
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
# (use the existing `client` and `auth_headers` fixtures from conftest)

def test_get_scientific_sources(client, auth_headers):
    resp = client.get("/scientific/sources", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    ids = [s["id"] for s in data]
    assert "crossref" in ids
    assert "pubmed" in ids
    assert "arxiv" in ids

def test_scientific_search_crossref(client, auth_headers):
    with patch("backend.adapters.scientific.crossref.CrossRefAdapter.search") as mock_search:
        from backend.adapters.scientific.base import ScientificRecord
        mock_search.return_value = [
            ScientificRecord(source_api="crossref", title="Test paper", doi="10.1234/test", year=2023)
        ]
        resp = client.post(
            "/scientific/search",
            json={"source": "crossref", "query": "CRISPR", "max_results": 5},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Test paper"

def test_scientific_import_creates_entities(client, auth_headers, db_session):
    with patch("backend.adapters.scientific.crossref.CrossRefAdapter.search") as mock_search:
        from backend.adapters.scientific.base import ScientificRecord
        mock_search.return_value = [
            ScientificRecord(
                source_api="crossref",
                title="Importable paper",
                doi="10.1234/importme",
                authors=["Smith, J."],
                year=2022,
                concepts=["biology"],
            )
        ]
        resp = client.post(
            "/scientific/import",
            json={"source": "crossref", "query": "biology", "max_results": 5},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["imported"] == 1
    assert body["skipped"] == 0

def test_scientific_doi_batch(client, auth_headers):
    with patch("backend.adapters.scientific.crossref.CrossRefAdapter.fetch_batch_dois") as mock_batch:
        from backend.adapters.scientific.base import ScientificRecord
        mock_batch.return_value = [
            ScientificRecord(source_api="crossref", title="Batched paper", doi="10.1234/batch", year=2021)
        ]
        resp = client.post(
            "/scientific/dois",
            json={"dois": ["10.1234/batch"], "source": "crossref"},
            headers=auth_headers,
        )
    assert resp.status_code == 201
    assert resp.json()["imported"] == 1

def test_scientific_search_unknown_source(client, auth_headers):
    resp = client.post(
        "/scientific/search",
        json={"source": "doesnotexist", "query": "anything"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run to fail**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -k "test_get_scientific_sources or test_scientific_search or test_scientific_import or test_scientific_doi" -v
```
Expected: FAILs (router not yet registered)

- [ ] **Step 3: Implement the router**

```python
# backend/routers/scientific_import.py
"""
Scientific literature import endpoints.
  GET  /scientific/sources              — list available sources
  POST /scientific/search               — search without importing
  POST /scientific/import               — search + save as RawEntity
  POST /scientific/dois                 — batch DOI resolver + save
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend import models
from backend.adapters.scientific import get_scientific_adapter, list_sources
from backend.adapters.scientific.base import ScientificRecord
from backend.parsers.science_mapper import science_record_to_entity
from backend.tenant_access import resolve_request_org_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scientific", tags=["scientific-import"])


class SearchRequest(BaseModel):
    source: str
    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=20, ge=1, le=100)
    config: dict = Field(default_factory=dict)   # API key, library_id, etc.


class DoiBatchRequest(BaseModel):
    dois: list[str] = Field(min_length=1, max_length=200)
    source: str = Field(default="crossref")
    config: dict = Field(default_factory=dict)


def _record_to_dict(r: ScientificRecord) -> dict:
    return {
        "title": r.title,
        "doi": r.doi,
        "authors": r.authors,
        "year": r.year,
        "abstract": r.abstract,
        "journal": r.journal,
        "publisher": r.publisher,
        "concepts": r.concepts,
        "citation_count": r.citation_count,
        "is_open_access": r.is_open_access,
        "url": r.url,
        "source_api": r.source_api,
        "external_id": r.external_id,
    }


def _save_records(
    records: list[ScientificRecord],
    db: Session,
    org_id: Optional[int],
) -> dict:
    """Convert ScientificRecords → RawEntity rows. Skips duplicates by DOI."""
    imported = 0
    skipped = 0
    for rec in records:
        if rec.doi:
            exists = db.query(models.RawEntity).filter_by(enrichment_doi=rec.doi).first()
            if exists:
                skipped += 1
                continue
        # Reuse the existing science_record_to_entity() mapper
        # Note: science_record_to_entity returns domain, primary_label, canonical_id,
        # secondary_label, entity_type, enrichment_concepts, attributes_json only.
        # enrichment_doi and enrichment_citation_count must be set explicitly.
        entity_kwargs = science_record_to_entity({
            "title": rec.title,
            "authors": "; ".join(rec.authors) if rec.authors else None,
            "doi": rec.doi,
            "keywords": ", ".join(rec.concepts) if rec.concepts else None,
            "year": str(rec.year) if rec.year else None,
            "abstract": rec.abstract,
            "journal": rec.journal,
            "publisher": rec.publisher,
        })
        entity_kwargs["enrichment_doi"] = rec.doi
        entity_kwargs["enrichment_citation_count"] = rec.citation_count or 0
        entity_kwargs["enrichment_source"] = rec.source_api
        entity_kwargs["source"] = "scientific_import"
        if org_id:
            entity_kwargs["org_id"] = org_id
        db.add(models.RawEntity(**entity_kwargs))
        imported += 1
    db.commit()
    return {"imported": imported, "skipped": skipped}


@router.get("/sources")
def get_sources(_=Depends(get_current_user)):
    return list_sources()


@router.post("/search")
def search_scientific(
    body: SearchRequest,
    _=Depends(get_current_user),
):
    try:
        adapter = get_scientific_adapter(body.source, body.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        records = adapter.search(body.query, max_results=body.max_results)
    except Exception as e:
        logger.exception("Scientific search failed for source=%s", body.source)
        raise HTTPException(status_code=502, detail=f"Source unavailable: {e}")
    return [_record_to_dict(r) for r in records]


@router.post("/import", status_code=201)
def import_scientific(
    body: SearchRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("super_admin", "admin", "editor")),
):
    try:
        adapter = get_scientific_adapter(body.source, body.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        records = adapter.search(body.query, max_results=body.max_results)
    except Exception as e:
        logger.exception("Scientific import failed for source=%s", body.source)
        raise HTTPException(status_code=502, detail=f"Source unavailable: {e}")
    org_id = resolve_request_org_id(db, current_user)
    return _save_records(records, db, org_id)


@router.post("/dois", status_code=201)
def import_dois(
    body: DoiBatchRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("super_admin", "admin", "editor")),
):
    try:
        adapter = get_scientific_adapter(body.source, body.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        records = adapter.fetch_batch_dois(body.dois)
    except Exception as e:
        logger.exception("DOI batch failed for source=%s", body.source)
        raise HTTPException(status_code=502, detail=f"Source unavailable: {e}")
    org_id = resolve_request_org_id(db, current_user)
    return _save_records(records, db, org_id)
```

- [ ] **Step 4: Register the router in main.py**

Find the block in `backend/main.py` where other routers are included (e.g., `app.include_router(ingest.router)`) and add:

```python
from backend.routers import scientific_import
# ...
app.include_router(scientific_import.router)
```

- [ ] **Step 5: Run all new tests**

```bash
.venv/Scripts/python -m pytest backend/tests/test_scientific_import.py -v
```
Expected: All PASSED (20+)

- [ ] **Step 6: Run full test suite to verify no regressions**

```bash
.venv/Scripts/python -m pytest backend/tests/ -x -q
```
Expected: All existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/scientific_import.py backend/main.py backend/tests/test_scientific_import.py
git commit -m "feat: add scientific import router with search, import and DOI batch endpoints"
```

---

## Task 9: Frontend — Scientific Import Page

**Files:**
- Create: `frontend/app/import/scientific/page.tsx`
- Modify: `frontend/app/components/Sidebar.tsx` (add nav item)

This page has 3 steps:
1. **Source + Query** — pick source, enter query (or paste DOIs for batch mode)
2. **Preview** — see results as a table before committing
3. **Import** — trigger import, show result

- [ ] **Step 1: Create the page**

```tsx
// frontend/app/import/scientific/page.tsx
"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api";

type Source = { id: string; name: string; requires_key: boolean };
type PreviewRecord = {
  title: string; doi: string | null; authors: string[]; year: number | null;
  journal: string | null; concepts: string[]; source_api: string;
};
type ImportResult = { imported: number; skipped: number };

type Step = "query" | "preview" | "done";

export default function ScientificImportPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [sourcesLoaded, setSourcesLoaded] = useState(false);
  const [source, setSource] = useState("crossref");
  const [mode, setMode] = useState<"search" | "dois">("search");
  const [query, setQuery] = useState("");
  const [doiText, setDoiText] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [libraryId, setLibraryId] = useState("");
  const [maxResults, setMaxResults] = useState(20);
  const [step, setStep] = useState<Step>("query");
  const [preview, setPreview] = useState<PreviewRecord[]>([]);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSources = async () => {
    if (sourcesLoaded) return;
    const resp = await apiFetch("/scientific/sources");
    const data: Source[] = await resp.json();
    setSources(data);
    setSourcesLoaded(true);
  };

  const selectedSource = sources.find((s) => s.id === source);

  const buildConfig = () => {
    const cfg: Record<string, string> = {};
    if (apiKey) cfg.api_key = apiKey;
    if (libraryId) cfg.library_id = libraryId;
    return cfg;
  };

  const handlePreview = async () => {
    setLoading(true);
    setError(null);
    try {
      let data: PreviewRecord[];
      if (mode === "dois") {
        const dois = doiText.split(/[\n,]+/).map((d) => d.trim()).filter(Boolean);
        const resp = await apiFetch("/scientific/search", {
          method: "POST",
          body: JSON.stringify({ source, query: dois.join(" "), max_results: dois.length, config: buildConfig() }),
        });
        data = await resp.json();
      } else {
        const resp = await apiFetch("/scientific/search", {
          method: "POST",
          body: JSON.stringify({ source, query, max_results: maxResults, config: buildConfig() }),
        });
        data = await resp.json();
      }
      setPreview(data);
      setStep("preview");
    } catch (e: any) {
      setError(e.message || "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async () => {
    setLoading(true);
    setError(null);
    try {
      let data: ImportResult;
      if (mode === "dois") {
        const dois = doiText.split(/[\n,]+/).map((d) => d.trim()).filter(Boolean);
        const resp = await apiFetch("/scientific/dois", {
          method: "POST",
          body: JSON.stringify({ dois, source, config: buildConfig() }),
        });
        data = await resp.json();
      } else {
        const resp = await apiFetch("/scientific/import", {
          method: "POST",
          body: JSON.stringify({ source, query, max_results: maxResults, config: buildConfig() }),
        });
        data = await resp.json();
      }
      setResult(data);
      setStep("done");
    } catch (e: any) {
      setError(e.message || "Import failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Scientific Import</h1>
        <p className="text-sm text-gray-500 mt-1">
          Search and import literature directly from PubMed, CrossRef, arXiv, DataCite, Zotero, or ORCID.
        </p>
      </div>

      {/* Progress */}
      <div className="flex gap-2 text-xs font-medium">
        {(["query", "preview", "done"] as Step[]).map((s, i) => (
          <span key={s} className={`px-3 py-1 rounded-full ${step === s ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"}`}>
            {i + 1}. {s.charAt(0).toUpperCase() + s.slice(1)}
          </span>
        ))}
      </div>

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Step 1: Query */}
      {step === "query" && (
        <div className="space-y-4 rounded-xl border border-gray-200 dark:border-gray-700 p-5 bg-white dark:bg-gray-900">
          <div onClick={loadSources} className="grid grid-cols-2 gap-3">
            {/* Source selector */}
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Source</label>
              <select
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2"
              >
                {sources.length === 0 && <option value="crossref">CrossRef</option>}
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}{s.requires_key ? " 🔑" : ""}</option>
                ))}
              </select>
            </div>
            {/* Mode */}
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Mode</label>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as "search" | "dois")}
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2"
              >
                <option value="search">Free-text search</option>
                <option value="dois">DOI batch import</option>
              </select>
            </div>
          </div>

          {/* API Key (if required) */}
          {selectedSource?.requires_key && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">API Key</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Your API key"
                  className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2"
                />
              </div>
              {source === "zotero" && (
                <div>
                  <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Library ID</label>
                  <input
                    type="text"
                    value={libraryId}
                    onChange={(e) => setLibraryId(e.target.value)}
                    placeholder="e.g. 12345"
                    className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2"
                  />
                </div>
              )}
            </div>
          )}

          {/* Query input */}
          {mode === "search" ? (
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                {source === "orcid" ? "ORCID iD (e.g. 0000-0002-1825-0097)" : "Search query"}
              </label>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={source === "orcid" ? "0000-0002-1825-0097" : "e.g. CRISPR gene editing 2023"}
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2"
              />
              <div className="mt-2 flex items-center gap-2 text-xs text-gray-500">
                <span>Max results:</span>
                <input
                  type="number"
                  min={1} max={100}
                  value={maxResults}
                  onChange={(e) => setMaxResults(Number(e.target.value))}
                  className="w-16 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-2 py-1 text-xs"
                />
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                DOIs (one per line or comma-separated)
              </label>
              <textarea
                value={doiText}
                onChange={(e) => setDoiText(e.target.value)}
                rows={6}
                placeholder={"10.1038/nature12373\n10.1016/j.cell.2022.01.001"}
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm px-3 py-2 font-mono"
              />
            </div>
          )}

          <button
            onClick={handlePreview}
            disabled={loading || (!query && mode === "search") || (!doiText && mode === "dois")}
            className="w-full rounded-md bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium py-2 px-4 transition-colors"
          >
            {loading ? "Searching…" : "Preview Results"}
          </button>
        </div>
      )}

      {/* Step 2: Preview */}
      {step === "preview" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600 dark:text-gray-400">{preview.length} records found</span>
            <button onClick={() => setStep("query")} className="text-xs text-indigo-600 hover:underline">← Change query</button>
          </div>
          <div className="overflow-auto rounded-xl border border-gray-200 dark:border-gray-700">
            <table className="min-w-full text-xs">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  {["Title", "Authors", "Year", "DOI", "Source"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-400">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {preview.map((r, i) => (
                  <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    <td className="px-3 py-2 max-w-xs truncate" title={r.title}>{r.title}</td>
                    <td className="px-3 py-2 text-gray-500">{(r.authors || []).slice(0, 2).join("; ")}{r.authors?.length > 2 ? " …" : ""}</td>
                    <td className="px-3 py-2 text-gray-500">{r.year ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-gray-500 max-w-[160px] truncate">{r.doi ?? "—"}</td>
                    <td className="px-3 py-2"><span className="rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 px-2 py-0.5">{r.source_api}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button
            onClick={handleImport}
            disabled={loading}
            className="w-full rounded-md bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium py-2 px-4 transition-colors"
          >
            {loading ? "Importing…" : `Import ${preview.length} records`}
          </button>
        </div>
      )}

      {/* Step 3: Done */}
      {step === "done" && result && (
        <div className="rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-6 text-center space-y-3">
          <div className="text-3xl font-bold text-green-700 dark:text-green-400">{result.imported}</div>
          <div className="text-sm text-green-700 dark:text-green-300">records imported successfully</div>
          {result.skipped > 0 && (
            <div className="text-xs text-gray-500">{result.skipped} skipped (already exist by DOI)</div>
          )}
          <div className="flex gap-3 justify-center pt-2">
            <a href="/entities" className="rounded-md bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-4 py-2">View Entities</a>
            <button onClick={() => { setStep("query"); setPreview([]); setResult(null); }} className="rounded-md border border-gray-300 dark:border-gray-600 text-sm px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-800">New Import</button>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add nav item to Sidebar**

In `frontend/app/components/Sidebar.tsx`, find the existing import-related nav items and add:

```tsx
{ href: "/import/scientific", label: "Scientific Import", icon: <BeakerIcon /> }
```

(Use whichever icon is available in the project — `FlaskConicalIcon`, `BeakerIcon`, `MicroscopeIcon`, or any equivalent from the icon library already used.)

- [ ] **Step 3: Start the dev server and verify visually**

```bash
cd D:/universal-knowledge-intelligence-platform/frontend
npm run dev
# Navigate to http://localhost:3004/import/scientific
```

Verify:
- Sources load in the dropdown
- Search mode works with a test query
- Preview table shows results
- Import button triggers the import endpoint

- [ ] **Step 4: Commit**

```bash
git add frontend/app/import/scientific/ frontend/app/components/Sidebar.tsx
git commit -m "feat: add Scientific Import page with source picker, preview, and import flow"
```

---

## Task 10: Final integration test + smoke test

- [ ] **Step 1: Run full backend test suite**

```bash
cd D:/universal-knowledge-intelligence-platform
.venv/Scripts/python -m pytest backend/tests/ -q
```
Expected: All existing tests pass + new scientific tests pass. Zero regressions.

- [ ] **Step 2: Verify OpenAPI docs include new endpoints**

Start the backend server and check:
```bash
.venv/Scripts/python -m uvicorn backend.main:app --reload --port 8000
# Visit http://localhost:8000/docs and confirm /scientific/* endpoints appear
```

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "feat: complete scientific connectors integration (CrossRef, PubMed, arXiv, DataCite, Zotero, ORCID)"
```

---

## Summary

| Component | Status |
|-----------|--------|
| `BaseScientificAdapter` + `ScientificRecord` | Task 1 |
| CrossRef adapter | Task 2 |
| PubMed adapter | Task 3 |
| arXiv adapter | Task 4 |
| DataCite adapter | Task 5 |
| Zotero adapter | Task 6 |
| ORCID Publications adapter | Task 7 |
| `/scientific/*` router | Task 8 |
| Frontend import page | Task 9 |
| Integration tests | Task 10 |

**Zero breaking changes:** All new files. Only `backend/main.py` and `frontend/app/components/Sidebar.tsx` are modified with additive changes only.
